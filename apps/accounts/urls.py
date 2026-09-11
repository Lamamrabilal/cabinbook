from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.accounts.views import (
    RegisterView, MeView, PractitionerViewSet, PatientViewSet, StaffAccountViewSet, RoomViewSet,
    PasswordResetRequestView, PasswordResetConfirmView, ContactMessageView,
    TwoFactorSetupView, TwoFactorConfirmView, TwoFactorDisableView,
    GoogleCalendarConnectView, GoogleCalendarCallbackView, GoogleCalendarDisconnectView,
)

router = DefaultRouter()
router.register("practitioners", PractitionerViewSet, basename="practitioner")
router.register("patients", PatientViewSet, basename="patient")
router.register("staff", StaffAccountViewSet, basename="staff")
router.register("rooms", RoomViewSet, basename="room")

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("me/", MeView.as_view(), name="me"),
    path("password-reset/", PasswordResetRequestView.as_view(), name="password-reset"),
    path("password-reset-confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("contact/", ContactMessageView.as_view(), name="contact"),
    path("2fa/setup/", TwoFactorSetupView.as_view(), name="2fa-setup"),
    path("2fa/confirm/", TwoFactorConfirmView.as_view(), name="2fa-confirm"),
    path("2fa/disable/", TwoFactorDisableView.as_view(), name="2fa-disable"),
    path("calendar/google/connect/", GoogleCalendarConnectView.as_view(), name="google-calendar-connect"),
    path("calendar/google/callback/", GoogleCalendarCallbackView.as_view(), name="google-calendar-callback"),
    path("calendar/google/disconnect/", GoogleCalendarDisconnectView.as_view(), name="google-calendar-disconnect"),
    path("", include(router.urls)),
]
