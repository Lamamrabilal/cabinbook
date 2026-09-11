from django.contrib import admin
from apps.appointments.models import (
    Appointment, TimeSlot, AppointmentSeries, SessionNote, WaitlistEntry, Review,
)


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("patient", "practitioner", "start_time", "end_time", "status", "series")
    list_filter = ("status", "practitioner")
    search_fields = ("patient__first_name", "patient__last_name")
    date_hierarchy = "start_time"


@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ("practitioner", "start_time", "end_time", "is_available")
    list_filter = ("is_available", "practitioner")


@admin.register(AppointmentSeries)
class AppointmentSeriesAdmin(admin.ModelAdmin):
    list_display = ("patient", "practitioner", "frequency", "first_start_time", "occurrences_total", "until", "is_active")
    list_filter = ("frequency", "is_active", "practitioner")
    search_fields = ("patient__first_name", "patient__last_name")


@admin.register(SessionNote)
class SessionNoteAdmin(admin.ModelAdmin):
    list_display = ("appointment", "created_at", "updated_at")


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("patient", "practitioner", "status", "created_at", "notified_at")
    list_filter = ("status", "practitioner")
    search_fields = ("patient__first_name", "patient__last_name")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("practitioner", "rating", "is_hidden", "created_at")
    list_filter = ("rating", "is_hidden", "practitioner")
