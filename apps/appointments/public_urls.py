from django.urls import path
from apps.appointments.public_views import (
    PublicPractitionerView,
    PublicBookingView,
    PublicConfirmView,
    PublicCancelView,
)

urlpatterns = [
    path("<slug:slug>/", PublicPractitionerView.as_view(), name="public-practitioner"),
    path("<slug:slug>/book/", PublicBookingView.as_view(), name="public-book"),
    path("confirm/<str:token>/", PublicConfirmView.as_view(), name="public-confirm"),
    path("cancel/<str:token>/", PublicCancelView.as_view(), name="public-cancel"),
]
