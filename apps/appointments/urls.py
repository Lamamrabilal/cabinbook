from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.appointments.views import AppointmentViewSet, TimeSlotViewSet

router = DefaultRouter()
router.register("", AppointmentViewSet, basename="appointment")
router.register("timeslots", TimeSlotViewSet, basename="timeslot")

urlpatterns = [
    path("", include(router.urls)),
]
