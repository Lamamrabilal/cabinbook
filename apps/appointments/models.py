from django.db import models
from apps.accounts.models import Practitioner, Patient, Room


class TimeSlot(models.Model):
    """Plage horaire disponible d'un praticien."""
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name="timeslots")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    is_available = models.BooleanField(default=True)
    blocked_by_external_calendar = models.BooleanField(
        default=False,
        help_text="Bloqué automatiquement car il chevauche un événement de l'agenda Google perso du praticien (pas un vrai RDV).",
    )

    class Meta:
        ordering = ["start_time"]
        indexes = [
            # Sélecteur de créneau (praticien) et page de réservation publique
            # filtrent toujours practitioner + is_available, triés par start_time.
            models.Index(
                fields=["practitioner", "is_available", "start_time"],
                name="slot_practitioner_avail_idx",
            ),
        ]

    def __str__(self):
        return f"{self.practitioner} — {self.start_time:%d/%m %H:%M}"


class AppointmentSeries(models.Model):
    """Série de rendez-vous récurrents (ex: séances hebdomadaires de kiné)."""
    FREQUENCY_WEEKLY = "weekly"
    FREQUENCY_BIWEEKLY = "biweekly"
    FREQUENCY_MONTHLY = "monthly"
    FREQUENCY_CHOICES = [
        (FREQUENCY_WEEKLY, "Toutes les semaines"),
        (FREQUENCY_BIWEEKLY, "Toutes les deux semaines"),
        (FREQUENCY_MONTHLY, "Tous les mois"),
    ]

    practitioner = models.ForeignKey(
        "accounts.Practitioner", on_delete=models.CASCADE, related_name="appointment_series"
    )
    patient = models.ForeignKey(
        "accounts.Patient", on_delete=models.CASCADE, related_name="appointment_series"
    )
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    first_start_time = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField()
    occurrences_total = models.PositiveIntegerField(null=True, blank=True)
    until = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Série de rendez-vous"
        verbose_name_plural = "Séries de rendez-vous"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Série {self.get_frequency_display()} — {self.patient} chez {self.practitioner}"


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
    series = models.ForeignKey(
        AppointmentSeries, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments"
    )
    series_position = models.PositiveIntegerField(null=True, blank=True)
    room = models.ForeignKey(
        Room, on_delete=models.SET_NULL, null=True, blank=True, related_name="appointments",
        help_text="Salle du cabinet occupée par ce RDV (optionnel, plan Cabinet).",
    )
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_CONFIRMED)
    reason = models.TextField(blank=True)
    notes = models.TextField(blank=True)  # notes internes praticien
    confirmation_token = models.CharField(max_length=64, unique=True, blank=True)
    cancellation_token = models.CharField(max_length=64, unique=True, blank=True)
    google_event_id = models.CharField(
        max_length=255, blank=True,
        help_text="ID de l'événement correspondant dans le Google Calendar du praticien, si connecté.",
    )

    # Rappels
    reminder_email_sent = models.BooleanField(default=False)
    reminder_sms_sent = models.BooleanField(default=False)
    reminder_whatsapp_sent = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-start_time"]
        verbose_name = "Rendez-vous"
        indexes = [
            # Agenda, stats et export iCal filtrent tous par practitioner (+ souvent
            # status), triés/filtrés par start_time.
            models.Index(fields=["practitioner", "start_time"], name="appt_practitioner_start_idx"),
            models.Index(
                fields=["practitioner", "status", "start_time"],
                name="appt_practitioner_status_idx",
            ),
        ]

    def __str__(self):
        return f"{self.patient} chez {self.practitioner} — {self.start_time:%d/%m/%Y %H:%M}"

    def save(self, *args, **kwargs):
        if not self.confirmation_token:
            import secrets
            self.confirmation_token = secrets.token_urlsafe(32)
            self.cancellation_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    @property
    def video_room_url(self):
        """Lien de téléconsultation Jitsi Meet — salle unique dérivée du token du RDV,
        sans compte ni clé API. Vide si le praticien n'a pas activé la téléconsultation."""
        if not self.practitioner.offers_teleconsultation:
            return ""
        room_slug = (self.confirmation_token or "")[:24]
        return f"https://meet.jit.si/CabinBook-{room_slug}" if room_slug else ""


class Review(models.Model):
    """Avis patient laissé après un rendez-vous terminé."""
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="review")
    practitioner = models.ForeignKey(
        "accounts.Practitioner", on_delete=models.CASCADE, related_name="reviews"
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    is_hidden = models.BooleanField(default=False, help_text="Masqué par le praticien (contenu inapproprié).")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Avis patient"
        verbose_name_plural = "Avis patients"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Avis {self.rating}/5 — {self.practitioner}"


class SessionNote(models.Model):
    """Note de séance structurée, liée à un rendez-vous précis (historique clinique léger)."""
    appointment = models.OneToOneField(Appointment, on_delete=models.CASCADE, related_name="session_note")
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Note de séance"
        verbose_name_plural = "Notes de séance"

    def __str__(self):
        return f"Note — {self.appointment}"


class WaitlistEntry(models.Model):
    """Patient en liste d'attente pour un créneau chez un praticien."""
    STATUS_WAITING = "waiting"
    STATUS_NOTIFIED = "notified"
    STATUS_BOOKED = "booked"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_WAITING, "En attente"),
        (STATUS_NOTIFIED, "Prévenu"),
        (STATUS_BOOKED, "Réservé"),
        (STATUS_CANCELLED, "Annulé"),
    ]

    practitioner = models.ForeignKey(
        "accounts.Practitioner", on_delete=models.CASCADE, related_name="waitlist_entries"
    )
    patient = models.ForeignKey(
        "accounts.Patient", on_delete=models.CASCADE, related_name="waitlist_entries"
    )
    notes = models.CharField(max_length=255, blank=True, help_text="Ex: disponible le matin uniquement")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_WAITING)
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entrée liste d'attente"
        verbose_name_plural = "Liste d'attente"
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.patient} — liste d'attente {self.practitioner}"


class AvailabilityRule(models.Model):
    """Règle récurrente de disponibilité d'un praticien (ex: tous les lundis 9h-18h)."""
    WEEKDAY_CHOICES = [
        (0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"),
        (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche"),
    ]

    practitioner = models.ForeignKey(
        "accounts.Practitioner", on_delete=models.CASCADE, related_name="availability_rules"
    )
    weekday = models.IntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    slot_duration_minutes = models.PositiveIntegerField(default=45)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Règle de disponibilité"
        unique_together = ("practitioner", "weekday")
        ordering = ["weekday", "start_time"]

    def __str__(self):
        return f"{self.practitioner} — {self.get_weekday_display()} {self.start_time}-{self.end_time}"
