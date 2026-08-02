from django.contrib import admin
from django.urls import path, include
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from cabinbook.views import LandingPageView, BookingPageView
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", LandingPageView.as_view(), name="landing"),

    # Auth JWT
    path("api/auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),

    # Apps
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/appointments/", include("apps.appointments.urls")),
    path("api/billing/", include("apps.billing.urls")),

    # API publique de réservation (JSON, appelée par le JS de la page de réservation)
    path("api/public/book/", include("apps.appointments.public_urls")),

    # Page HTML publique de réservation (vue par le patient dans le navigateur)
    path("book/<slug:slug>/", BookingPageView.as_view(), name="booking-page"),
]
