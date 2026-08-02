from django.contrib import admin
from apps.accounts.models import User, Practitioner, Patient


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ("email", "first_name", "last_name", "plan", "is_subscription_active", "created_at")
    search_fields = ("email", "first_name", "last_name")


@admin.register(Practitioner)
class PractitionerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "specialty", "owner", "is_active", "created_at")
    search_fields = ("first_name", "last_name", "email")
    list_filter = ("is_active", "specialty")


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "email", "phone", "practitioner", "created_at")
    search_fields = ("first_name", "last_name", "email")
    list_filter = ("practitioner",)
