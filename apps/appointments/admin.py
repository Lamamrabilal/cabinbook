from django.contrib import admin
from apps.appointments.models import Appointment, TimeSlot


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "practitioner", "start_time", "end_time", "status")
    list_filter = ("status", "practitioner")
    search_fields = ("patient__first_name", "patient__last_name")
    date_hierarchy = "start_time"


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("practitioner", "start_time", "end_time", "is_available")
    list_filter = ("is_available", "practitioner")
