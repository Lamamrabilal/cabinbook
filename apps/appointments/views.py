import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.appointments.models import Appointment, TimeSlot
from apps.appointments.serializers import (
    AppointmentListSerializer,
    AppointmentDetailSerializer,
    TimeSlotSerializer,
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
        # Seulement les créneaux des praticiens de l'utilisateur connecté
        return TimeSlot.objects.filter(
            practitioner__owner=self.request.user
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
            practitioner__owner=self.request.user
        ).select_related("patient", "practitioner__owner")

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
        return Response({"status": "annulé"})

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
