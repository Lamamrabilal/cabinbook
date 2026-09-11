from django.db import models


class Invoice(models.Model):
    """Note d'honoraires émise pour un rendez-vous (facturation patient)."""
    STATUS_UNPAID = "unpaid"
    STATUS_PAID = "paid"
    STATUS_REFUNDED = "refunded"
    STATUS_CHOICES = [
        (STATUS_UNPAID, "Non payée"),
        (STATUS_PAID, "Payée"),
        (STATUS_REFUNDED, "Remboursée"),
    ]

    appointment = models.OneToOneField(
        "appointments.Appointment", on_delete=models.CASCADE, related_name="invoice"
    )
    amount_cents = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_UNPAID)
    stripe_checkout_session_id = models.CharField(max_length=200, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    refunded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Note d'honoraires"
        verbose_name_plural = "Notes d'honoraires"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Facture #{self.pk} — {self.appointment}"
