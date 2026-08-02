from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounts.views import RegisterView, MeView, PractitionerViewSet, PatientViewSet

router = DefaultRouter()
router.register("practitioners", PractitionerViewSet, basename="practitioner")
router.register("patients", PatientViewSet, basename="patient")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("", include(router.urls)),
]
