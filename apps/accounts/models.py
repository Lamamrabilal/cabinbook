from django.contrib.auth.models import AbstractUser
from django.db import models
from apps.accounts.fields import EncryptedCharField


class User(AbstractUser):
    """Utilisateur de base — praticien ou admin."""
    PLAN_STARTER = "starter"
    PLAN_PRO = "pro"
    PLAN_CABINET = "cabinet"
    PLAN_CHOICES = [
        (PLAN_STARTER, "Starter — 29€/mois"),
        (PLAN_PRO, "Pro — 49€/mois"),
        (PLAN_CABINET, "Cabinet — 99€/mois"),
    ]

    ROLE_OWNER = "owner"
    ROLE_SECRETARY = "secretary"
    ROLE_CHOICES = [
        (ROLE_OWNER, "Titulaire"),
        (ROLE_SECRETARY, "Secrétaire"),
    ]

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_STARTER)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    is_subscription_active = models.BooleanField(default=False)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_OWNER)
    owner_account = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="staff_members",
        help_text="Pour un compte secrétaire : le titulaire pour le compte duquel il agit.",
    )
    otp_secret = EncryptedCharField(
        max_length=32, blank=True,
        help_text="Secret TOTP (authentification à deux facteurs), chiffré en base.",
    )
    otp_enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        verbose_name = "Utilisateur"

    def __str__(self):
        return self.email

    @property
    def max_practitioners(self):
        return {"starter": 1, "pro": 1, "cabinet": 5}.get(self.plan, 1)

    @property
    def max_staff(self):
        """Nombre de comptes secrétaire autorisés selon le plan du titulaire."""
        return {"starter": 0, "pro": 1, "cabinet": 3}.get(self.plan, 0)

    @property
    def effective_owner(self):
        """Le titulaire pour le compte duquel agit cet utilisateur (lui-même, sauf pour un compte secrétaire)."""
        if self.role == self.ROLE_SECRETARY and self.owner_account_id:
            return self.owner_account
        return self


class Practitioner(models.Model):
    """Praticien rattaché à un compte (utile pour plan Cabinet)."""
    SPECIALTY_CHOICES = [
        ("kine", "Kinésithérapeute"),
        ("osteo", "Ostéopathe"),
        ("psy", "Psychologue"),
        ("infirmier", "Infirmier libéral"),
        ("autre", "Autre"),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="practitioners")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    specialty = models.CharField(max_length=30, choices=SPECIALTY_CHOICES)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    booking_page_slug = models.SlugField(unique=True)
    city = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)
    is_listed = models.BooleanField(
        default=True, help_text="Visible dans l'annuaire public de recherche."
    )
    consultation_price_cents = models.PositiveIntegerField(
        default=0, help_text="Tarif de consultation en centimes (0 = non renseigné). Utilisé pour pré-remplir les notes d'honoraires."
    )
    deposit_amount_cents = models.PositiveIntegerField(
        default=0,
        help_text="Acompte en centimes exigé à la réservation en ligne (0 = aucun acompte requis).",
    )
    offers_teleconsultation = models.BooleanField(
        default=False,
        help_text="Si activé, un lien de visioconférence (Jitsi Meet) est proposé sur chaque rendez-vous.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Praticien"

    def __str__(self):
        return f"Dr {self.last_name} ({self.get_specialty_display()})"


class Room(models.Model):
    """Salle physique du cabinet, partagée entre praticiens (plan Cabinet)."""
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="rooms")
    name = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Salle"
        unique_together = ("owner", "name")

    def __str__(self):
        return self.name


class GoogleCalendarConnection(models.Model):
    """
    Connexion OAuth d'un praticien à son Google Calendar personnel, utilisée
    pour pousser automatiquement ses RDV confirmés (synchro sortante) et pour
    bloquer les créneaux qui chevauchent un événement de son agenda perso
    (synchro entrante, anti double-booking).
    """
    practitioner = models.OneToOneField(
        Practitioner, on_delete=models.CASCADE, related_name="google_calendar_connection"
    )
    google_email = models.EmailField(blank=True)
    access_token = EncryptedCharField(max_length=512)
    refresh_token = EncryptedCharField(max_length=512)
    token_expiry = models.DateTimeField()
    calendar_id = models.CharField(max_length=255, default="primary")
    sync_busy_from_google = models.BooleanField(
        default=True,
        help_text="Bloquer les créneaux CabinBook qui chevauchent un événement de l'agenda Google perso.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Connexion Google Calendar"

    def __str__(self):
        return f"Google Calendar — {self.practitioner} ({self.google_email})"


class Patient(models.Model):
    """Patient associé à un praticien."""
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name="patients")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    carte_vitale_number = EncryptedCharField(
        max_length=15, blank=True,
        help_text="Numero de securite sociale (15 chiffres) - donnee sensible, chiffree en base.",
    )
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Patient"
        unique_together = ("practitioner", "email")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
