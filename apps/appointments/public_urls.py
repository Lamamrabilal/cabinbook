from django.urls import path
from apps.appointments.public_views import (
    PublicPractitionerView,
    PublicBookingView,
    PublicConfirmView,
    PublicCancelView,
    PublicReviewView,
)

urlpatterns = [
    path("review/<str:token>/", PublicReviewView.as_view(), name="public-review"),
    path("confirm/<str:token>/", PublicConfirmView.as_view(), name="public-confirm"),
    path("cancel/<str:token>/", PublicCancelView.as_view(), name="public-cancel"),
    path("<slug:slug>/", PublicPractitionerView.as_view(), name="public-practitioner"),
    path("<slug:slug>/book/", PublicBookingView.as_view(), name="public-book"),
]
