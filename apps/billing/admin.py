from django.contrib import admin
from apps.billing.models import Invoice


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("appointment", "amount_cents", "status", "paid_at", "created_at")
    list_filter = ("status",)
