from django.contrib import admin
from django.urls import path, include
from apps.accounts.views import CookieTokenObtainPairView, CookieTokenRefreshView, LogoutView
from cabinbook.views import (
    LandingPageView, BookingPageView, MentionsLegalesView, PolitiqueConfidentialiteView,
    ContactPageView, AnnuaireView, ReviewPageView,
)
urlpatterns = [
    path("admin/", admin.site.urls),
    path("", LandingPageView.as_view(), name="landing"),
    path("mentions-legales/", MentionsLegalesView.as_view(), name="mentions-legales"),
    path("politique-de-confidentialite/", PolitiqueConfidentialiteView.as_view(), name="politique-confidentialite"),
    path("contact/", ContactPageView.as_view(), name="contact-page"),
    path("annuaire/", AnnuaireView.as_view(), name="annuaire"),
    path("avis/<str:token>/", ReviewPageView.as_view(), name="review-page"),

    # Auth JWT (cookies httpOnly)
    path("api/auth/token/", CookieTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("api/auth/token/refresh/", CookieTokenRefreshView.as_view(), name="token_refresh"),
    path("api/auth/logout/", LogoutView.as_view(), name="logout"),

    # Apps
    path("api/accounts/", include("apps.accounts.urls")),
    path("api/appointments/", include("apps.appointments.urls")),
    path("api/billing/", include("apps.billing.urls")),

    # API publique de réservation (JSON, appelée par le JS de la page de réservation)
    path("api/public/book/", include("apps.appointments.public_urls")),
    # API publique de l'annuaire (recherche par ville/spécialité)
    path("api/public/directory/", include("apps.accounts.public_urls")),

    # Page HTML publique de réservation (vue par le patient dans le navigateur)
    path("book/<slug:slug>/", BookingPageView.as_view(), name="booking-page"),
]
