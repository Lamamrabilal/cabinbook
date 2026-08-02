from django.contrib.auth.models import AbstractUser
from django.db import models


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

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default=PLAN_STARTER)
    stripe_customer_id = models.CharField(max_length=100, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True)
    is_subscription_active = models.BooleanField(default=False)
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
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Praticien"

    def __str__(self):
        return f"Dr {self.last_name} ({self.get_specialty_display()})"


class Patient(models.Model):
    """Patient associé à un praticien."""
    practitioner = models.ForeignKey(Practitioner, on_delete=models.CASCADE, related_name="patients")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Patient"
        unique_together = ("practitioner", "email")

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
