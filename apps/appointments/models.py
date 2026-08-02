from django.db import models
from apps.accounts.models import Practitioner, Patient


class TimeSlot(models.Model):
    """Plage horaire disponible d'un praticien."""
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name="timeslots")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)

    class Meta:
        ordering = ["start_time"]

    def __str__(self):
        return f"{self.practitioner} — {self.start_time:%d/%m %H:%M}"


class Appointment(models.Model):
    """Rendez-vous entre praticien et patient."""
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_CANCELLED = "cancelled"
    STATUS_NO_SHOW = "no_show"
    STATUS_DONE = "done"
    STATUS_CHOICES = [
        (STATUS_PENDING, "En attente"),
        (STATUS_CONFIRMED, "Confirmé"),
        (STATUS_CANCELLED, "Annulé"),
        (STATUS_NO_SHOW, "Absent"),
        (STATUS_DONE, "Terminé"),
    ]

    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name="appointments")
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="appointments")
    timeslot = models.OneToOneField(TimeSlot, on_delete=models.SET_NULL, null=True, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)  # notes internes praticien
    confirmation_token = models.CharField(max_length=64, unique=True, blank=True)
    cancellation_token = models.CharField(max_length=64, unique=True, blank=True)

    # Rappels
    reminder_email_sent = models.BooleanField(default=False)
    reminder_sms_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_time"]
        verbose_name = "Rendez-vous"

    def __str__(self):
        return f"{self.patient} chez {self.practitioner} — {self.start_time:%d/%m/%Y %H:%M}"

    def save(self, *args, **kwargs):
        if not self.confirmation_token:
            import secrets
            self.confirmation_token = secrets.token_urlsafe(32)
            self.cancellation_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)
