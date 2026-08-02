from rest_framework import serializers
from django.utils import timezone
from apps.appointments.models import Appointment, TimeSlot
from apps.accounts.serializers import PatientSerializer, PractitionerSerializer


class TimeSlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeSlot
        fields = ["id", "practitioner", "start_time", "end_time", "is_available"]
        read_only_fields = ["is_available"]

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

    class Meta:
        model = Appointment
        fields = [
            "id", "patient_name", "practitioner_name",
            "start_time", "end_time", "status", "status_display",
        ]

    def get_patient_name(self, obj):
        return f"{obj.patient.first_name} {obj.patient.last_name}"


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
            "reason", "notes",
            "reminder_email_sent", "reminder_sms_sent",
            "confirmation_token", "cancellation_token",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "reminder_email_sent", "reminder_sms_sent",
            "confirmation_token", "cancellation_token",
            "created_at", "updated_at",
        ]

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
