import stripe
import logging
from django.conf import settings
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class CreateCheckoutSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        plan = request.data.get("plan", "starter")
        price_id = settings.STRIPE_PRICES.get(plan)

        if not price_id:
            return Response({"error": "Plan invalide."}, status=400)

        try:
            # Créer ou récupérer le customer Stripe
            user = request.user
            if not user.stripe_customer_id:
                customer = stripe.Customer.create(email=user.email, name=user.get_full_name())
                user.stripe_customer_id = customer.id
                user.save(update_fields=["stripe_customer_id"])

            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
                metadata={"user_id": str(user.pk), "plan": plan},
            )
            return Response({"checkout_url": session.url})

        except stripe.error.StripeError as e:
            logger.error("Stripe error: %s", e)
            return Response({"error": str(e)}, status=400)


class StripeWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Stripe n'a pas de session/CSRF token

    def post(self, request):
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, settings.STRIPE_WEBHOOK_SECRET)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            logger.warning("Webhook invalide : %s", e)
            return HttpResponse(status=400)

        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "customer.subscription.deleted": self._handle_subscription_deleted,
            "invoice.payment_failed": self._handle_payment_failed,
        }

        handler = handlers.get(event["type"])
        if handler:
            handler(event["data"]["object"])

        return HttpResponse(status=200)

    def _handle_checkout_completed(self, session):
        from apps.accounts.models import User
        user_id = session["metadata"].get("user_id")
        plan = session["metadata"].get("plan", "starter")
        try:
            user = User.objects.get(pk=user_id)
            user.plan = plan
            user.stripe_subscription_id = session.get("subscription", "")
            user.is_subscription_active = True
            user.save(update_fields=["plan", "stripe_subscription_id", "is_subscription_active"])
            logger.info("Subscription activée pour user %s (plan: %s)", user_id, plan)
        except User.DoesNotExist:
            logger.error("User %s introuvable lors du checkout.", user_id)

    def _handle_subscription_deleted(self, subscription):
        from apps.accounts.models import User
        try:
            user = User.objects.get(stripe_subscription_id=subscription["id"])
            user.is_subscription_active = False
            user.save(update_fields=["is_subscription_active"])
            logger.info("Subscription annulée pour user %s", user.pk)
        except User.DoesNotExist:
            pass

    def _handle_payment_failed(self, invoice):
        logger.warning("Paiement échoué pour customer %s", invoice.get("customer"))
