import stripe
import logging
from django.conf import settings
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.accounts.permissions import IsAccountOwner
from apps.billing.models import Invoice
from apps.billing.serializers import InvoiceSerializer

stripe.api_key = settings.STRIPE_SECRET_KEY
logger = logging.getLogger(__name__)


class InvoiceViewSet(viewsets.ModelViewSet):
    """Notes d'honoraires (facturation patient) — création, suivi de paiement.
    Accessible aux comptes secrétaire (facturation front-desk), à la différence
    de l'abonnement SaaS lui-même (CreateCheckoutSessionView/CancelSubscriptionView,
    réservés au titulaire)."""
    serializer_class = InvoiceSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Invoice.objects.filter(
            appointment__practitioner__owner=self.request.user.effective_owner
        ).select_related("appointment__patient", "appointment__practitioner")
        appointment_id = self.request.query_params.get("appointment")
        if appointment_id:
            qs = qs.filter(appointment_id=appointment_id)
        return qs

    @action(detail=True, methods=["post"])
    def mark_paid(self, request, pk=None):
        """Enregistre un paiement effectué hors ligne (espèces, carte en cabinet...)."""
        from django.utils import timezone
        invoice = self.get_object()
        if invoice.status == Invoice.STATUS_REFUNDED:
            return Response({"error": "Cette facture a été remboursée."}, status=400)
        invoice.status = Invoice.STATUS_PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at"])
        return Response(InvoiceSerializer(invoice).data)

    @action(detail=True, methods=["post"])
    def create_payment_link(self, request, pk=None):
        """Crée une session de paiement Stripe (paiement unique) pour cette facture."""
        invoice = self.get_object()
        if invoice.status in (Invoice.STATUS_PAID, Invoice.STATUS_REFUNDED):
            return Response({"error": "Cette facture est déjà payée ou a été remboursée."}, status=400)

        practitioner = invoice.appointment.practitioner
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": "eur",
                        "unit_amount": invoice.amount_cents,
                        "product_data": {"name": f"Consultation — {practitioner}"},
                    },
                    "quantity": 1,
                }],
                customer_email=invoice.appointment.patient.email or None,
                success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
                metadata={"invoice_id": str(invoice.pk)},
            )
        except stripe.error.StripeError as e:
            logger.error("Erreur création lien de paiement facture %s: %s", invoice.pk, e)
            return Response({"error": str(e)}, status=400)

        invoice.stripe_checkout_session_id = session.id
        invoice.save(update_fields=["stripe_checkout_session_id"])
        return Response({"checkout_url": session.url})

    @action(detail=True, methods=["post"])
    def refund(self, request, pk=None):
        """
        Rembourse une facture payée. Si elle a été payée via Stripe (acompte
        à la réservation ou lien de paiement), déclenche un vrai remboursement
        Stripe sur le paiement d'origine. Si elle a été marquée payée
        manuellement (espèces, carte en cabinet), il n'y a rien à rembourser
        via l'API — seul le statut est mis à jour, le remboursement se fait
        hors ligne.
        """
        from django.utils import timezone
        invoice = self.get_object()
        if invoice.status != Invoice.STATUS_PAID:
            return Response({"error": "Seule une facture payée peut être remboursée."}, status=400)

        if invoice.stripe_checkout_session_id:
            try:
                session = stripe.checkout.Session.retrieve(invoice.stripe_checkout_session_id)
                payment_intent = session.get("payment_intent")
                if payment_intent:
                    stripe.Refund.create(payment_intent=payment_intent)
            except stripe.error.StripeError as e:
                logger.error("Erreur remboursement Stripe facture %s: %s", invoice.pk, e)
                return Response({"error": str(e)}, status=400)

        invoice.status = Invoice.STATUS_REFUNDED
        invoice.refunded_at = timezone.now()
        invoice.save(update_fields=["status", "refunded_at"])
        logger.info("Facture %s remboursée par user %s", invoice.pk, request.user.pk)
        return Response(InvoiceSerializer(invoice).data)


class CreateCheckoutSessionView(APIView):
    """Réservé au titulaire du compte — un compte secrétaire ne gère pas l'abonnement SaaS."""
    permission_classes = [IsAuthenticated, IsAccountOwner]

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

            # Si un abonnement actif ou en essai existe deja, on le MODIFIE
            # (changement de plan) au lieu d'en creer un nouveau, pour eviter
            # d'avoir plusieurs abonnements simultanes pour le meme praticien.
            if user.stripe_subscription_id:
                try:
                    existing = stripe.Subscription.retrieve(user.stripe_subscription_id)
                except stripe.error.InvalidRequestError:
                    existing = None

                if existing is not None and existing.get("status") in ("active", "trialing"):
                    if existing["items"]["data"][0]["price"]["id"] == price_id:
                        return Response({"message": "Vous etes deja sur ce plan.", "plan": plan})

                    item_id = existing["items"]["data"][0]["id"]
                    stripe.Subscription.modify(
                        user.stripe_subscription_id,
                        items=[{"id": item_id, "price": price_id}],
                        proration_behavior="create_prorations",
                        metadata={"user_id": str(user.pk), "plan": plan},
                    )
                    user.plan = plan
                    user.is_subscription_active = True
                    user.save(update_fields=["plan", "is_subscription_active"])
                    logger.info("Plan change directement pour user %s -> %s", user.pk, plan)
                    return Response({
                        "message": f"Votre abonnement a ete mis a jour vers le plan {plan}.",
                        "plan": plan,
                    })

            # L'essai gratuit ne s'applique qu'a la toute premiere souscription.
            # Si l'utilisateur a deja eu un abonnement Stripe (changement de plan,
            # reabonnement...), on ne raccorde pas de nouvel essai.
            is_first_subscription = not user.stripe_subscription_id
            subscription_data = {"metadata": {"user_id": str(user.pk), "plan": plan}}
            if is_first_subscription:
                subscription_data["trial_period_days"] = 30

            session = stripe.checkout.Session.create(
                customer=user.stripe_customer_id,
                payment_method_types=["card"],
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                subscription_data=subscription_data,
                success_url=f"{settings.FRONTEND_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/billing/cancel",
                metadata={"user_id": str(user.pk), "plan": plan},
            )
            return Response({"checkout_url": session.url})

        except stripe.error.StripeError as e:
            logger.error("Stripe error: %s", e)
            return Response({"error": str(e)}, status=400)


class CancelSubscriptionView(APIView):
    """Le praticien resilie son abonnement (effectif a la fin de la periode en cours,
    y compris pendant l'essai gratuit — aucun prelevement n'aura lieu).
    Réservé au titulaire du compte."""
    permission_classes = [IsAuthenticated, IsAccountOwner]

    def post(self, request):
        user = request.user
        if not user.stripe_subscription_id:
            return Response({"error": "Aucun abonnement actif a resilier."}, status=400)

        try:
            subscription = stripe.Subscription.modify(
                user.stripe_subscription_id,
                cancel_at_period_end=True,
            )
            return Response({
                "message": "Votre abonnement sera resilie a la fin de la periode en cours. Aucun prelevement ne sera effectue.",
                "cancel_at": subscription.get("cancel_at"),
            })
        except stripe.error.StripeError as e:
            logger.error("Erreur annulation abonnement: %s", e)
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
        invoice_id = (session.get("metadata") or {}).get("invoice_id")
        if invoice_id:
            self._handle_invoice_paid(invoice_id)
            return

        from apps.accounts.models import User
        from apps.notifications.services import EmailService
        user_id = session["metadata"].get("user_id")
        plan = session["metadata"].get("plan", "starter")
        try:
            user = User.objects.get(pk=user_id)
            user.plan = plan
            user.stripe_subscription_id = session.get("subscription", "")
            user.is_subscription_active = True
            user.save(update_fields=["plan", "stripe_subscription_id", "is_subscription_active"])
            logger.info("Subscription activée pour user %s (plan: %s)", user_id, plan)
            try:
                EmailService.send_subscription_confirmation(user, plan)
            except Exception as exc:
                logger.error("Erreur envoi email confirmation abonnement: %s", exc)
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

    def _handle_invoice_paid(self, invoice_id):
        from django.utils import timezone
        from apps.appointments.models import Appointment
        try:
            invoice = Invoice.objects.select_related("appointment").get(pk=invoice_id)
        except Invoice.DoesNotExist:
            logger.error("Invoice %s introuvable lors du webhook checkout.", invoice_id)
            return
        invoice.status = Invoice.STATUS_PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at"])

        # Acompte à la réservation : le RDV était en attente du paiement, on le confirme
        # maintenant et on envoie l'email de confirmation (non envoyé au moment de la
        # réservation, puisque le paiement restait à faire).
        appointment = invoice.appointment
        if appointment.status == Appointment.STATUS_PENDING:
            appointment.status = Appointment.STATUS_CONFIRMED
            appointment.save(update_fields=["status", "updated_at"])
            if appointment.patient.email:
                try:
                    from apps.notifications.services import EmailService
                    EmailService.send_confirmation(appointment)
                except Exception as exc:
                    logger.warning("Email confirmation (post-acompte) échoué pour RDV %s: %s", appointment.pk, exc)
            logger.info("RDV %s confirmé après paiement de l'acompte (facture %s)", appointment.pk, invoice.pk)
        logger.info("Facture %s marquée payée via Stripe.", invoice.pk)
