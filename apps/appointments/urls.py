from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.appointments.views import (
    AppointmentViewSet, TimeSlotViewSet, AvailabilityRuleViewSet, AppointmentSeriesViewSet,
    WaitlistEntryViewSet, ReviewViewSet,
)

router = DefaultRouter()
router.register("timeslots", TimeSlotViewSet, basename="timeslot")
router.register("availability-rules", AvailabilityRuleViewSet, basename="availability-rule")
router.register("series", AppointmentSeriesViewSet, basename="appointment-series")
router.register("waitlist", WaitlistEntryViewSet, basename="waitlist-entry")
router.register("reviews", ReviewViewSet, basename="review")
router.register("", AppointmentViewSet, basename="appointment")

urlpatterns = [
    path("", include(router.urls)),
]
