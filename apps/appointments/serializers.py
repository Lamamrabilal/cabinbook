from rest_framework import serializers
from django.utils import timezone
from apps.appointments.models import (
    Appointment, TimeSlot, AvailabilityRule, AppointmentSeries, SessionNote, WaitlistEntry, Review,
)
from apps.accounts.serializers import PatientSerializer, PractitionerSerializer


class TimeSlotSerializer(serializers.ModelSerializer):
    practitioner_name = serializers.CharField(source="practitioner.__str__", read_only=True)

    class Meta:
        model = TimeSlot
        fields = ["id", "practitioner", "practitioner_name", "start_time", "end_time", "is_available"]
        read_only_fields = ["is_available", "practitioner_name"]

    def validate_practitioner(self, practitioner):
        request = self.context.get("request")
        if request and practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Praticien non autorisé.")
        return practitioner

    def validate(self, attrs):
        if attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début.")
        if attrs["start_time"] < timezone.now():
            raise serializers.ValidationError("Impossible de créer un créneau dans le passé.")
        # Vérifier chevauchement
        overlapping = TimeSlot.objects.filter(
            practitioner=attrs["practitioner"],
            start_time__lt=attrs["end_time"],
            end_time__gt=attrs["start_time"],
        )
        if self.instance:
            overlapping = overlapping.exclude(pk=self.instance.pk)
        if overlapping.exists():
            raise serializers.ValidationError("Ce créneau chevauche un créneau existant.")
        return attrs


class AppointmentListSerializer(serializers.ModelSerializer):
    """Serializer léger pour les listes (calendrier)."""
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.CharField(source="practitioner.__str__", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    series_total = serializers.SerializerMethodField()
    has_note = serializers.SerializerMethodField()
    room_name = serializers.CharField(source="room.name", read_only=True, default=None)

    class Meta:
        model = Appointment
        fields = [
            "id", "patient_name", "practitioner_name",
            "start_time", "end_time", "status", "status_display",
            "series", "series_position", "series_total", "has_note",
            "video_room_url", "room", "room_name",
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"

    def get_series_total(self, obj):
        if not obj.series_id:
            return None
        return obj.series.occurrences_total

    def get_has_note(self, obj):
        return hasattr(obj, "session_note")


class AppointmentDetailSerializer(serializers.ModelSerializer):
    """Serializer complet pour création/détail."""
    patient = PatientSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__("apps.accounts.models", fromlist=["Patient"]).Patient.objects.all(),
        source="patient",
        write_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id", "practitioner", "patient", "patient_id",
            "start_time", "end_time", "status", "status_display",
            "reason", "notes", "series", "series_position",
            "reminder_email_sent", "reminder_sms_sent",
            "confirmation_token", "cancellation_token", "video_room_url", "room",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "series", "series_position",
            "reminder_email_sent", "reminder_sms_sent",
            "confirmation_token", "cancellation_token",
            "created_at", "updated_at",
        ]

    def validate_practitioner(self, practitioner):
        """
        Empêche de créer ou de réassigner un RDV à un praticien d'un autre
        cabinet — sans ça, un titulaire pourrait, via un simple PATCH,
        déplacer un de ses RDV (avec le patient, les notes, le motif) dans
        l'agenda d'un praticien appartenant à un autre compte.
        """
        request = self.context.get("request")
        if request and practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Praticien non autorisé.")
        return practitioner

    def validate(self, attrs):
        practitioner = attrs.get("practitioner", getattr(self.instance, "practitioner", None))
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))

        if end and start and end <= start:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début.")

        if start and start < timezone.now() and not self.instance:
            raise serializers.ValidationError("Impossible de créer un RDV dans le passé.")

        # Vérifier chevauchement pour ce praticien
        if practitioner and start and end:
            overlapping = Appointment.objects.filter(
                practitioner=practitioner,
                status__in=[Appointment.STATUS_CONFIRMED, Appointment.STATUS_PENDING],
                start_time__lt=end,
                end_time__gt=start,
            )
            if self.instance:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            if overlapping.exists():
                raise serializers.ValidationError(
                    "Un rendez-vous existe déjà sur ce créneau pour ce praticien."
                )

        # Vérifier que le patient appartient bien au praticien
        patient = attrs.get("patient")
        if patient and practitioner and patient.practitioner != practitioner:
            raise serializers.ValidationError("Ce patient n'appartient pas à ce praticien.")

        # Salle (optionnelle) : doit appartenir au même cabinet, et ne pas être
        # déjà occupée par un autre RDV (tous praticiens confondus) sur ce créneau.
        room = attrs.get("room", getattr(self.instance, "room", None) if self.instance else None)
        if room and practitioner and practitioner.owner_id != room.owner_id:
            raise serializers.ValidationError("Cette salle n'appartient pas à ce cabinet.")
        if room and start and end:
            room_overlap = Appointment.objects.filter(
                room=room,
                status__in=[Appointment.STATUS_CONFIRMED, Appointment.STATUS_PENDING],
                start_time__lt=end,
                end_time__gt=start,
            )
            if self.instance:
                room_overlap = room_overlap.exclude(pk=self.instance.pk)
            if room_overlap.exists():
                raise serializers.ValidationError("Cette salle est déjà occupée sur ce créneau.")

        return attrs

    def create(self, validated_data):
        appointment = super().create(validated_data)
        # Envoyer confirmation immédiate
        from apps.notifications.services import EmailService
        if appointment.patient.email:
            try:
                EmailService.send_confirmation(appointment)
            except Exception:
                pass  # Ne pas bloquer la création si l'email échoue
        return appointment

class SessionNoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionNote
        fields = ["id", "appointment", "content", "created_at", "updated_at"]
        read_only_fields = ["appointment", "created_at", "updated_at"]


class WaitlistEntrySerializer(serializers.ModelSerializer):
    patient = PatientSerializer(read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__("apps.accounts.models", fromlist=["Patient"]).Patient.objects.all(),
        source="patient", write_only=True,
    )
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = WaitlistEntry
        fields = [
            "id", "practitioner", "patient", "patient_id", "notes",
            "status", "status_display", "notified_at", "created_at",
        ]
        read_only_fields = ["status", "notified_at", "created_at"]

    def validate_practitioner(self, practitioner):
        request = self.context.get("request")
        if request and practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Praticien non autorisé.")
        return practitioner

    def validate(self, attrs):
        patient = attrs.get("patient")
        practitioner = attrs.get("practitioner")
        if patient and practitioner and patient.practitioner != practitioner:
            raise serializers.ValidationError("Ce patient n'appartient pas à ce praticien.")
        return attrs


class ReviewSerializer(serializers.ModelSerializer):
    patient_name = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = [
            "id", "practitioner", "rating", "comment", "is_hidden", "created_at", "patient_name",
        ]
        read_only_fields = ["practitioner", "rating", "comment", "created_at", "patient_name"]

    def get_patient_name(self, obj):
        p = obj.appointment.patient
        return f"{p.first_name} {p.last_name[0]}."


class AppointmentSeriesSerializer(serializers.ModelSerializer):
    """Lecture d'une série + création (validation des paramètres de récurrence)."""
    frequency_display = serializers.CharField(source="get_frequency_display", read_only=True)
    patient_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__("apps.accounts.models", fromlist=["Patient"]).Patient.objects.all(),
        source="patient", write_only=True,
    )
    patient = PatientSerializer(read_only=True)

    class Meta:
        model = AppointmentSeries
        fields = [
            "id", "practitioner", "patient", "patient_id", "frequency", "frequency_display",
            "first_start_time", "duration_minutes", "occurrences_total", "until",
            "reason", "is_active", "created_at",
        ]
        read_only_fields = ["is_active", "created_at"]

    MAX_OCCURRENCES = 52
    MAX_HORIZON_DAYS = 548  # ~18 mois

    def validate_practitioner(self, practitioner):
        request = self.context.get("request")
        if request and practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Praticien non autorisé.")
        return practitioner

    def validate(self, attrs):
        if attrs["duration_minutes"] <= 0:
            raise serializers.ValidationError("La durée doit être positive.")
        if attrs["first_start_time"] < timezone.now():
            raise serializers.ValidationError("Impossible de créer une série dans le passé.")

        occurrences_total = attrs.get("occurrences_total")
        until = attrs.get("until")
        if bool(occurrences_total) == bool(until):
            raise serializers.ValidationError(
                "Indiquez soit un nombre de séances, soit une date de fin — pas les deux, pas aucun."
            )
        if occurrences_total and occurrences_total > self.MAX_OCCURRENCES:
            raise serializers.ValidationError(f"Une série ne peut pas dépasser {self.MAX_OCCURRENCES} séances.")
        if until:
            horizon = (until - attrs["first_start_time"].date()).days
            if horizon > self.MAX_HORIZON_DAYS:
                raise serializers.ValidationError("Une série ne peut pas s'étendre sur plus de 18 mois.")
            if horizon < 0:
                raise serializers.ValidationError("La date de fin doit être après la première séance.")

        patient = attrs.get("patient")
        practitioner = attrs.get("practitioner")
        if patient and practitioner and patient.practitioner != practitioner:
            raise serializers.ValidationError("Ce patient n'appartient pas à ce praticien.")

        return attrs


class AvailabilityRuleSerializer(serializers.ModelSerializer):
    weekday_display = serializers.CharField(source="get_weekday_display", read_only=True)

    class Meta:
        model = AvailabilityRule
        fields = [
            "id", "practitioner", "weekday", "weekday_display",
            "start_time", "end_time", "slot_duration_minutes", "is_active",
        ]

    def validate_practitioner(self, practitioner):
        request = self.context.get("request")
        if request and practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Praticien non autorisé.")
        return practitioner

    def validate(self, attrs):
        start = attrs.get("start_time", getattr(self.instance, "start_time", None))
        end = attrs.get("end_time", getattr(self.instance, "end_time", None))
        if start and end and end <= start:
            raise serializers.ValidationError("L'heure de fin doit être après l'heure de début.")
        return attrs
