import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework import serializers as drf_serializers

from apps.accounts.models import Practitioner, Patient
from apps.appointments.models import Appointment, TimeSlot, Review

logger = logging.getLogger(__name__)


# --- Serializers publics (sans JWT) ---

class PublicPractitionerSerializer(drf_serializers.ModelSerializer):
    specialty_display = drf_serializers.CharField(source="get_specialty_display", read_only=True)

    class Meta:
        model = Practitioner
        fields = ["id", "first_name", "last_name", "specialty_display", "booking_page_slug", "deposit_amount_cents"]


class PublicSlotSerializer(drf_serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ["id", "start_time", "end_time"]


class PublicBookingSerializer(drf_serializers.Serializer):
    first_name = drf_serializers.CharField(max_length=100)
    last_name = drf_serializers.CharField(max_length=100)
    email = drf_serializers.EmailField()
    phone = drf_serializers.CharField(max_length=20, required=False, allow_blank=True)
    timeslot_id = drf_serializers.IntegerField()
    reason = drf_serializers.CharField(max_length=500, required=False, allow_blank=True)


# --- Vues publiques ---

class PublicPractitionerView(APIView):
    """
    GET /book/<slug>/
    Retourne le profil public + créneaux disponibles.
    """
    permission_classes = [AllowAny]

    def get(self, request, slug):
        practitioner = get_object_or_404(Practitioner, booking_page_slug=slug, is_active=True)

        # Vérifier que la souscription est active
        if not practitioner.owner.is_subscription_active:
            return Response({"error": "Ce praticien n'est pas disponible pour la réservation en ligne."}, status=503)

        now = timezone.now()
        slots = TimeSlot.objects.filter(
            practitioner=practitioner,
            is_available=True,
            start_time__gte=now,
        ).order_by("start_time")[:60]  # max 60 créneaux affichés

        return Response({
            "practitioner": PublicPractitionerSerializer(practitioner).data,
            "available_slots": PublicSlotSerializer(slots, many=True).data,
        })


class PublicBookingView(APIView):
    """
    POST /book/<slug>/book/
    Prend un RDV sans authentification.
    """
    permission_classes = [AllowAny]

    def post(self, request, slug):
        practitioner = get_object_or_404(Practitioner, booking_page_slug=slug, is_active=True)

        if not practitioner.owner.is_subscription_active:
            return Response({"error": "Réservation en ligne indisponible."}, status=503)

        serializer = PublicBookingSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data

        with transaction.atomic():
            # Récupérer le créneau et le verrouiller
            try:
                slot = TimeSlot.objects.select_for_update().get(
                    pk=data["timeslot_id"],
                    practitioner=practitioner,
                    is_available=True,
                )
            except TimeSlot.DoesNotExist:
                return Response({"error": "Ce créneau n'est plus disponible."}, status=409)

            if slot.start_time < timezone.now():
                return Response({"error": "Ce créneau n'est plus disponible."}, status=409)

            # Créer ou récupérer le patient
            patient, _ = Patient.objects.get_or_create(
                practitioner=practitioner,
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "phone": data.get("phone", ""),
                },
            )

            # Si un acompte est exigé, le RDV reste en attente jusqu'au paiement.
            requires_deposit = practitioner.deposit_amount_cents > 0
            appointment = Appointment.objects.create(
                practitioner=practitioner,
                patient=patient,
                timeslot=slot,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status=Appointment.STATUS_PENDING if requires_deposit else Appointment.STATUS_CONFIRMED,
                reason=data.get("reason", ""),
            )

            # Marquer le créneau comme réservé (y compris pendant l'attente de paiement,
            # pour éviter un double-booking le temps que le patient paie).
            slot.is_available = False
            slot.save(update_fields=["is_available"])

            if requires_deposit:
                from apps.billing.models import Invoice
                invoice = Invoice.objects.create(
                    appointment=appointment, amount_cents=practitioner.deposit_amount_cents,
                )

        if requires_deposit:
            import stripe

            base_url = request.build_absolute_uri(f"/book/{slug}/")
            try:
                session = stripe.checkout.Session.create(
                    mode="payment",
                    payment_method_types=["card"],
                    line_items=[{
                        "price_data": {
                            "currency": "eur",
                            "unit_amount": invoice.amount_cents,
                            "product_data": {"name": f"Acompte — RDV avec {practitioner}"},
                        },
                        "quantity": 1,
                    }],
                    customer_email=patient.email or None,
                    success_url=f"{base_url}?deposit=success",
                    cancel_url=f"{base_url}?deposit=cancelled",
                    metadata={"invoice_id": str(invoice.pk), "appointment_id": str(appointment.pk)},
                )
            except stripe.error.StripeError as e:
                logger.error("Erreur creation session acompte pour RDV %s: %s", appointment.pk, e)
                return Response(
                    {"error": "Impossible de démarrer le paiement de l'acompte. Réessayez dans un instant."},
                    status=502,
                )
            invoice.stripe_checkout_session_id = session.id
            invoice.save(update_fields=["stripe_checkout_session_id"])

            logger.info("Nouveau RDV #%s (en attente d'acompte) via page publique (%s)", appointment.pk, slug)
            return Response({
                "message": "Un acompte est requis pour confirmer ce rendez-vous.",
                "requires_payment": True,
                "checkout_url": session.url,
                "appointment": {
                    "id": appointment.pk,
                    "start_time": appointment.start_time,
                    "end_time": appointment.end_time,
                    "practitioner": str(practitioner),
                    "cancellation_token": appointment.cancellation_token,
                    "video_room_url": appointment.video_room_url,
                },
            }, status=201)

        # Envoyer confirmation email
        from apps.notifications.services import EmailService
        if patient.email:
            try:
                EmailService.send_confirmation(appointment)
            except Exception as e:
                logger.warning("Email confirmation échoué : %s", e)

        logger.info("Nouveau RDV #%s via page publique (%s)", appointment.pk, slug)

        return Response({
            "message": "Votre rendez-vous est confirmé !",
            "requires_payment": False,
            "appointment": {
                "id": appointment.pk,
                "start_time": appointment.start_time,
                "end_time": appointment.end_time,
                "practitioner": str(practitioner),
                "cancellation_token": appointment.cancellation_token,
                "video_room_url": appointment.video_room_url,
            }
        }, status=201)


class PublicConfirmView(APIView):
    """GET /book/confirm/<token>/ — Patient confirme sa présence via email."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        appointment = get_object_or_404(Appointment, confirmation_token=token)
        if appointment.status == Appointment.STATUS_CONFIRMED:
            return Response({"message": "Votre présence est bien confirmée. À bientôt !"})
        return Response({"error": "Ce rendez-vous ne peut pas être confirmé."}, status=400)


class PublicCancelView(APIView):
    """GET /book/cancel/<token>/ — Patient annule via lien email."""
    permission_classes = [AllowAny]

    def get(self, request, token):
        appointment = get_object_or_404(Appointment, cancellation_token=token)
        if appointment.status in [Appointment.STATUS_DONE, Appointment.STATUS_CANCELLED]:
            return Response({"error": "Ce rendez-vous est déjà annulé ou terminé."}, status=400)

        appointment.status = Appointment.STATUS_CANCELLED
        appointment.save(update_fields=["status", "updated_at"])

        if appointment.timeslot:
            appointment.timeslot.is_available = True
            appointment.timeslot.save(update_fields=["is_available"])

        logger.info("RDV #%s annulé via lien public", appointment.pk)
        return Response({"message": "Votre rendez-vous a bien été annulé."})


class PublicReviewView(APIView):
    """
    GET  /book/review/<token>/ — infos du RDV pour afficher le formulaire d'avis.
    POST /book/review/<token>/ — soumission de l'avis { rating: 1-5, comment: "" }.
    Le token est le confirmation_token du RDV (déjà connu du patient via les emails).
    """
    permission_classes = [AllowAny]

    def get(self, request, token):
        appointment = get_object_or_404(Appointment, confirmation_token=token)
        if appointment.status != Appointment.STATUS_DONE:
            return Response({"error": "Cet avis n'est disponible qu'après la séance."}, status=400)
        existing = getattr(appointment, "review", None)
        return Response({
            "practitioner": PublicPractitionerSerializer(appointment.practitioner).data,
            "already_reviewed": existing is not None,
            "existing_rating": existing.rating if existing else None,
            "existing_comment": existing.comment if existing else "",
        })

    def post(self, request, token):
        appointment = get_object_or_404(Appointment, confirmation_token=token)
        if appointment.status != Appointment.STATUS_DONE:
            return Response({"error": "Cet avis n'est disponible qu'après la séance."}, status=400)
        if hasattr(appointment, "review"):
            return Response({"error": "Vous avez déjà laissé un avis pour cette séance."}, status=400)

        rating = request.data.get("rating")
        try:
            rating = int(rating)
        except (TypeError, ValueError):
            rating = None
        if not rating or rating < 1 or rating > 5:
            return Response({"error": "La note doit être comprise entre 1 et 5."}, status=400)

        review = Review.objects.create(
            appointment=appointment,
            practitioner=appointment.practitioner,
            rating=rating,
            comment=(request.data.get("comment") or "")[:2000],
        )
        logger.info("Avis %s/5 déposé pour RDV #%s", rating, appointment.pk)
        return Response({"message": "Merci pour votre avis !"}, status=201)
