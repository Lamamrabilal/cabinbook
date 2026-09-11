import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.appointments.models import (
    Appointment, TimeSlot, AvailabilityRule, AppointmentSeries, SessionNote, WaitlistEntry, Review,
)
from apps.appointments.serializers import (
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    TimeSlotSerializer,
    AvailabilityRuleSerializer,
    AppointmentSeriesSerializer,
    SessionNoteSerializer,
    WaitlistEntrySerializer,
    ReviewSerializer,
)

logger = logging.getLogger(__name__)


class TimeSlotViewSet(viewsets.ModelViewSet):
    """CRUD créneaux horaires d'un praticien."""
    serializer_class = TimeSlotSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["practitioner", "is_available"]
    ordering = ["start_time"]

    def get_queryset(self):
        # Seulement les créneaux futurs des praticiens de l'utilisateur connecté
        # (un créneau déjà passé n'a plus de sens à proposer, notamment dans le
        # sélecteur de créneau de la prise de RDV manuelle).
        return TimeSlot.objects.filter(
            practitioner__owner=self.request.user.effective_owner,
            start_time__gte=timezone.now(),
        ).select_related("practitioner")


class AppointmentViewSet(viewsets.ModelViewSet):
    """CRUD rendez-vous avec actions métier."""
    permission_classes = [IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["practitioner", "status", "patient"]
    search_fields = ["patient__first_name", "patient__last_name", "patient__email"]
    ordering_fields = ["start_time", "created_at", "status"]
    ordering = ["-start_time"]

    def get_queryset(self):
        qs = Appointment.objects.filter(
            practitioner__owner=self.request.user.effective_owner
        ).select_related("patient", "practitioner__owner", "series")

        # Filtre optionnel par praticien precis (compte multi-praticiens)
        practitioner_id = self.request.query_params.get("practitioner")
        if practitioner_id:
            qs = qs.filter(practitioner_id=practitioner_id)

        # Filtre optionnel par plage de dates
        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        if date_from:
            qs = qs.filter(start_time__gte=date_from)
        if date_to:
            qs = qs.filter(start_time__lte=date_to)

        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return AppointmentListSerializer
        return AppointmentDetailSerializer

    # --- Actions métier ---

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        """Confirme un RDV en attente."""
        appt = self.get_object()
        if appt.status != Appointment.STATUS_PENDING:
            return Response({"error": "Seul un RDV en attente peut être confirmé."}, status=400)
        appt.status = Appointment.STATUS_CONFIRMED
        appt.save(update_fields=["status"])
        logger.info("RDV %s confirmé par user %s", appt.pk, request.user.pk)
        return Response({"status": "confirmé"})

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Annule un RDV."""
        appt = self.get_object()
        if appt.status in [Appointment.STATUS_DONE, Appointment.STATUS_CANCELLED]:
            return Response({"error": "Ce RDV ne peut plus être annulé."}, status=400)
        appt.status = Appointment.STATUS_CANCELLED
        appt.save(update_fields=["status", "updated_at"])
        # Libérer le créneau si lié
        if appt.timeslot:
            appt.timeslot.is_available = True
            appt.timeslot.save(update_fields=["is_available"])
        logger.info("RDV %s annulé par user %s", appt.pk, request.user.pk)
        _notify_next_waitlist_entry(appt.practitioner)
        return Response({"status": "annulé"})

    @action(detail=True, methods=["get", "post"])
    def note(self, request, pk=None):
        """
        GET : renvoie la note de séance existante (ou vide si aucune).
        POST : crée ou met à jour la note. Payload: { "content": "..." }
        Réservé au praticien titulaire — un compte secrétaire n'a pas accès
        aux notes de séance (données cliniques sensibles).
        """
        if request.user.role == request.user.ROLE_SECRETARY:
            raise PermissionDenied("Les notes de séance sont réservées au praticien titulaire.")
        appt = self.get_object()
        if request.method == "GET":
            existing = getattr(appt, "session_note", None)
            return Response(SessionNoteSerializer(existing).data if existing else {"content": ""})

        content = request.data.get("content", "")
        note, _ = SessionNote.objects.update_or_create(
            appointment=appt, defaults={"content": content}
        )
        return Response(SessionNoteSerializer(note).data)

    @action(detail=True, methods=["post"])
    def no_show(self, request, pk=None):
        """Marque un patient absent."""
        appt = self.get_object()
        appt.status = Appointment.STATUS_NO_SHOW
        appt.save(update_fields=["status", "updated_at"])
        return Response({"status": "absent"})

    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        """Marque un RDV comme terminé."""
        appt = self.get_object()
        appt.status = Appointment.STATUS_DONE
        appt.save(update_fields=["status", "updated_at"])
        if appt.patient.email:
            try:
                from apps.notifications.services import EmailService
                EmailService.send_review_request(appt)
            except Exception:
                logger.exception("Échec de l'email de demande d'avis pour le RDV %s", appt.pk)
        return Response({"status": "terminé"})

    @action(detail=False, methods=["get"])
    def today(self, request):
        """RDV du jour pour le dashboard."""
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now.replace(hour=23, minute=59, second=59)
        qs = self.get_queryset().filter(
            start_time__range=(today_start, today_end)
        ).exclude(status=Appointment.STATUS_CANCELLED)
        serializer = AppointmentListSerializer(qs, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Statistiques rapides pour le dashboard."""
        qs = self.get_queryset()
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)

        return Response({
            "total_month": qs.filter(start_time__gte=month_start).count(),
            "confirmed": qs.filter(status=Appointment.STATUS_CONFIRMED).count(),
            "no_shows_month": qs.filter(
                start_time__gte=month_start,
                status=Appointment.STATUS_NO_SHOW
            ).count(),
            "upcoming_today": qs.filter(
                start_time__gte=now,
                start_time__date=now.date(),
                status=Appointment.STATUS_CONFIRMED,
            ).count(),
        })

    @action(detail=False, methods=["get"])
    def stats_by_practitioner(self, request):
        """
        GET /api/appointments/stats_by_practitioner/
        Statistiques comparatives par praticien (RDV du mois, confirmes,
        no-shows, taux de remplissage). Reserve au plan Cabinet.
        """
        from apps.accounts.models import Practitioner

        owner = request.user.effective_owner
        if owner.plan != "cabinet":
            return Response(
                {"error": "Les statistiques par praticien sont reservees au plan Cabinet."},
                status=403,
            )

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        practitioners = Practitioner.objects.filter(owner=owner)
        results = []
        for p in practitioners:
            qs = Appointment.objects.filter(practitioner=p, start_time__gte=month_start)
            total = qs.count()
            confirmed = qs.filter(status=Appointment.STATUS_CONFIRMED).count()
            no_shows = qs.filter(status=Appointment.STATUS_NO_SHOW).count()
            done = qs.filter(status=Appointment.STATUS_DONE).count()
            fill_rate = round((done + confirmed) / total * 100) if total else 0
            results.append({
                "practitioner_id": p.id,
                "practitioner_name": f"{p.first_name} {p.last_name}",
                "specialty": p.specialty,
                "total_month": total,
                "confirmed": confirmed,
                "no_shows": no_shows,
                "done": done,
                "fill_rate": fill_rate,
            })

        return Response(results)

    @action(detail=False, methods=["get"])
    def export_ical(self, request):
        """
        GET /api/appointments/export_ical/
        Exporte les rendez-vous confirmes du praticien au format iCal (.ics).
        Reserve aux plans Pro et Cabinet.
        """
        from django.http import HttpResponse
        from icalendar import Calendar, Event

        owner = request.user.effective_owner
        if owner.plan not in ("pro", "cabinet"):
            return Response(
                {"error": "L'export iCal est reserve aux plans Pro et Cabinet."},
                status=403,
            )

        qs = self.get_queryset().exclude(status=Appointment.STATUS_CANCELLED)

        cal = Calendar()
        cal.add("prodid", "-//CabinBook//Export Agenda//FR")
        cal.add("version", "2.0")
        cal.add("x-wr-calname", "CabinBook — Rendez-vous")

        for appt in qs:
            event = Event()
            event.add("uid", f"appointment-{appt.pk}@cabinbook")
            event.add("summary", f"RDV — {appt.patient}")
            event.add("dtstart", appt.start_time)
            event.add("dtend", appt.end_time)
            event.add("dtstamp", timezone.now())
            if appt.reason:
                event.add("description", appt.reason)
            cal.add_component(event)

        response = HttpResponse(cal.to_ical(), content_type="text/calendar")
        response["Content-Disposition"] = "attachment; filename=cabinbook-agenda.ics"
        return response

    @action(detail=False, methods=["post"])
    def book_manual(self, request):
        """
        Le praticien enregistre lui-meme un RDV pour un patient
        (ex: prise de rendez-vous par telephone), en choisissant
        un creneau disponible existant.
        Payload: { timeslot_id, patient_id (existant) OU
                   patient: {first_name, last_name, email, phone},
                   reason (optionnel) }
        """
        from django.db import transaction
        from apps.appointments.models import TimeSlot
        from apps.accounts.models import Patient

        timeslot_id = request.data.get("timeslot_id")
        if not timeslot_id:
            return Response({"error": "timeslot_id est requis."}, status=400)

        with transaction.atomic():
            try:
                slot = TimeSlot.objects.select_for_update().get(
                    pk=timeslot_id,
                    practitioner__owner=request.user.effective_owner,
                    is_available=True,
                )
            except TimeSlot.DoesNotExist:
                return Response({"error": "Ce creneau n'est plus disponible."}, status=409)

            if slot.start_time < timezone.now():
                return Response({"error": "Ce creneau n'est plus disponible."}, status=409)

            patient_id = request.data.get("patient_id")
            if patient_id:
                try:
                    patient = Patient.objects.get(pk=patient_id, practitioner=slot.practitioner)
                except Patient.DoesNotExist:
                    return Response({"error": "Patient introuvable pour ce praticien."}, status=404)
            else:
                patient_data = request.data.get("patient") or {}
                email = patient_data.get("email", "")
                if not email or not patient_data.get("first_name") or not patient_data.get("last_name"):
                    return Response(
                        {"error": "patient_id, ou patient {first_name, last_name, email}, est requis."},
                        status=400,
                    )
                patient, _ = Patient.objects.get_or_create(
                    practitioner=slot.practitioner,
                    email=email,
                    defaults={
                        "first_name": patient_data["first_name"],
                        "last_name": patient_data["last_name"],
                        "phone": patient_data.get("phone", ""),
                    },
                )

            room = None
            room_id = request.data.get("room_id")
            if room_id:
                from apps.accounts.models import Room
                try:
                    room = Room.objects.get(pk=room_id, owner=slot.practitioner.owner)
                except Room.DoesNotExist:
                    return Response({"error": "Salle introuvable pour ce cabinet."}, status=404)
                room_busy = Appointment.objects.filter(
                    room=room,
                    status__in=[Appointment.STATUS_CONFIRMED, Appointment.STATUS_PENDING],
                    start_time__lt=slot.end_time,
                    end_time__gt=slot.start_time,
                ).exists()
                if room_busy:
                    return Response({"error": "Cette salle est déjà occupée sur ce créneau."}, status=409)

            appointment = Appointment.objects.create(
                practitioner=slot.practitioner,
                patient=patient,
                timeslot=slot,
                room=room,
                start_time=slot.start_time,
                end_time=slot.end_time,
                status=Appointment.STATUS_CONFIRMED,
                reason=request.data.get("reason", ""),
            )

            slot.is_available = False
            slot.save(update_fields=["is_available"])

        logger.info("RDV %s enregistre manuellement par user %s", appointment.pk, request.user.pk)
        serializer = AppointmentListSerializer(appointment)
        return Response(serializer.data, status=201)


def _notify_next_waitlist_entry(practitioner):
    """Prévient le premier patient en attente qu'un créneau vient de se libérer chez ce praticien."""
    entry = WaitlistEntry.objects.filter(
        practitioner=practitioner, status=WaitlistEntry.STATUS_WAITING
    ).select_related("patient").first()
    if not entry:
        return
    entry.status = WaitlistEntry.STATUS_NOTIFIED
    entry.notified_at = timezone.now()
    entry.save(update_fields=["status", "notified_at"])
    if entry.patient.email:
        try:
            from apps.notifications.services import EmailService
            EmailService.send_waitlist_notification(entry)
        except Exception:
            logger.exception("Échec de l'email de notification liste d'attente pour l'entrée %s", entry.pk)


def _add_months(dt, n):
    """Ajoute n mois à dt, en calant sur le dernier jour du mois si besoin (ex: 31 janv. + 1 mois -> 28/29 fevrier)."""
    import calendar
    month_index = dt.month - 1 + n
    year = dt.year + month_index // 12
    month = month_index % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def _series_occurrence_dates(first_start_time, frequency, occurrences_total, until):
    """Calcule les dates de début de chaque occurrence de la série."""
    from datetime import timedelta

    step = {
        AppointmentSeries.FREQUENCY_WEEKLY: timedelta(weeks=1),
        AppointmentSeries.FREQUENCY_BIWEEKLY: timedelta(weeks=2),
    }.get(frequency)

    dates = []
    current = first_start_time
    while True:
        if occurrences_total and len(dates) >= occurrences_total:
            break
        if until and current.date() > until:
            break
        dates.append(current)
        if frequency == AppointmentSeries.FREQUENCY_MONTHLY:
            current = _add_months(current, 1)
        else:
            current = current + step
        # Garde-fou anti-boucle infinie si ni occurrences_total ni until n'aboutissent (ne devrait pas arriver, validé en amont).
        if len(dates) > AppointmentSeriesSerializer.MAX_OCCURRENCES:
            break
    return dates


class AppointmentSeriesViewSet(viewsets.ModelViewSet):
    """Création et gestion des séries de rendez-vous récurrents (plans Pro et Cabinet)."""
    serializer_class = AppointmentSeriesSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AppointmentSeries.objects.filter(
            practitioner__owner=self.request.user.effective_owner
        ).select_related("practitioner", "patient").prefetch_related("appointments")

    def create(self, request, *args, **kwargs):
        from django.db import transaction
        from datetime import timedelta

        owner = request.user.effective_owner
        if owner.plan not in ("pro", "cabinet"):
            return Response(
                {"error": "Les séries de rendez-vous récurrents sont réservées aux plans Pro et Cabinet."},
                status=403,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        practitioner = serializer.validated_data["practitioner"]
        if practitioner.owner != owner:
            raise PermissionDenied("Praticien non autorisé.")

        duration = timedelta(minutes=serializer.validated_data["duration_minutes"])
        dates = _series_occurrence_dates(
            serializer.validated_data["first_start_time"],
            serializer.validated_data["frequency"],
            serializer.validated_data.get("occurrences_total"),
            serializer.validated_data.get("until"),
        )

        created = []
        conflicts = []
        with transaction.atomic():
            series = serializer.save()
            for position, start in enumerate(dates, start=1):
                end = start + duration
                overlapping = Appointment.objects.select_for_update().filter(
                    practitioner=practitioner,
                    status__in=[Appointment.STATUS_CONFIRMED, Appointment.STATUS_PENDING],
                    start_time__lt=end,
                    end_time__gt=start,
                ).exists()
                if overlapping:
                    conflicts.append({"series_position": position, "date": start, "reason": "Créneau déjà occupé"})
                    continue

                appointment = Appointment.objects.create(
                    practitioner=practitioner,
                    patient=series.patient,
                    series=series,
                    series_position=position,
                    start_time=start,
                    end_time=end,
                    status=Appointment.STATUS_CONFIRMED,
                    reason=series.reason,
                )
                created.append(appointment)

                if appointment.patient.email:
                    try:
                        from apps.notifications.services import EmailService
                        EmailService.send_confirmation(appointment)
                    except Exception:
                        pass  # Ne pas bloquer la création de la série si l'email échoue

        logger.info(
            "Série %s créée par user %s : %d séances créées, %d conflits.",
            series.pk, request.user.pk, len(created), len(conflicts),
        )
        return Response({
            "series": AppointmentSeriesSerializer(series).data,
            "created": AppointmentListSerializer(created, many=True).data,
            "conflicts": conflicts,
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """
        Annule les séances de la série. Payload optionnel: { "scope": "future" | "all" }
        "future" (par défaut) : n'annule que les séances à venir non déjà terminées.
        "all" : annule aussi les séances passées encore en attente/confirmées (correction de saisie).
        """
        series = self.get_object()
        scope = request.data.get("scope", "future")
        if scope not in ("future", "all"):
            return Response({"error": "scope doit être 'future' ou 'all'."}, status=400)

        qs = series.appointments.filter(
            status__in=[Appointment.STATUS_PENDING, Appointment.STATUS_CONFIRMED]
        )
        if scope == "future":
            qs = qs.filter(start_time__gte=timezone.now())

        cancelled_count = 0
        for appt in qs.select_related("timeslot"):
            appt.status = Appointment.STATUS_CANCELLED
            appt.save(update_fields=["status", "updated_at"])
            if appt.timeslot:
                appt.timeslot.is_available = True
                appt.timeslot.save(update_fields=["is_available"])
            cancelled_count += 1

        series.is_active = False
        series.save(update_fields=["is_active"])

        logger.info("Série %s annulée (scope=%s) par user %s : %d séances annulées.", series.pk, scope, request.user.pk, cancelled_count)
        return Response({"status": "annulée", "cancelled_count": cancelled_count})


class AvailabilityRuleViewSet(viewsets.ModelViewSet):
    """CRUD des règles de disponibilité récurrentes d'un praticien."""
    serializer_class = AvailabilityRuleSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return AvailabilityRule.objects.filter(
            practitioner__owner=self.request.user.effective_owner
        ).select_related("practitioner")

    def perform_create(self, serializer):
        practitioner = serializer.validated_data["practitioner"]
        if practitioner.owner != self.request.user.effective_owner:
            raise PermissionDenied("Praticien non autorisé.")
        rule = serializer.save()
        self._generate_slots_now(rule)

    def perform_update(self, serializer):
        rule = serializer.save()
        self._generate_slots_now(rule)

    @staticmethod
    def _generate_slots_now(rule):
        """
        Génère immédiatement les créneaux de cette règle (au lieu d'attendre
        le prochain passage de la tâche planifiée à 6h) — sans quoi une règle
        créée ou réactivée en cours de journée ne serait réservable qu'à
        partir du lendemain.
        """
        if not rule.is_active:
            return
        from apps.notifications.tasks import generate_slots_for_rule
        generate_slots_for_rule(rule)


class WaitlistEntryViewSet(viewsets.ModelViewSet):
    """Gestion de la liste d'attente d'un praticien."""
    serializer_class = WaitlistEntrySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = WaitlistEntry.objects.filter(
            practitioner__owner=self.request.user.effective_owner
        ).select_related("practitioner", "patient")
        practitioner_id = self.request.query_params.get("practitioner")
        if practitioner_id:
            qs = qs.filter(practitioner_id=practitioner_id)
        status_param = self.request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)
        return qs

    def perform_create(self, serializer):
        practitioner = serializer.validated_data["practitioner"]
        if practitioner.owner != self.request.user.effective_owner:
            raise PermissionDenied("Praticien non autorisé.")
        serializer.save()

    @action(detail=True, methods=["post"])
    def notify(self, request, pk=None):
        """Envoie manuellement l'email de notification à cette entrée (créneau disponible)."""
        entry = self.get_object()
        entry.status = WaitlistEntry.STATUS_NOTIFIED
        entry.notified_at = timezone.now()
        entry.save(update_fields=["status", "notified_at"])
        if entry.patient.email:
            try:
                from apps.notifications.services import EmailService
                EmailService.send_waitlist_notification(entry)
            except Exception:
                return Response({"status": "prévenu", "email_error": True})
        return Response({"status": "prévenu"})

    @action(detail=True, methods=["post"])
    def mark_booked(self, request, pk=None):
        entry = self.get_object()
        entry.status = WaitlistEntry.STATUS_BOOKED
        entry.save(update_fields=["status"])
        return Response({"status": "réservé"})


class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    """Consultation des avis reçus par ses praticiens (modération : masquer un avis inapproprié)."""
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Review.objects.filter(practitioner__owner=self.request.user.effective_owner).select_related(
            "practitioner", "appointment__patient"
        )
        practitioner_id = self.request.query_params.get("practitioner")
        if practitioner_id:
            qs = qs.filter(practitioner_id=practitioner_id)
        return qs

    @action(detail=True, methods=["post"])
    def toggle_hidden(self, request, pk=None):
        review = self.get_object()
        review.is_hidden = not review.is_hidden
        review.save(update_fields=["is_hidden"])
        return Response(ReviewSerializer(review).data)
