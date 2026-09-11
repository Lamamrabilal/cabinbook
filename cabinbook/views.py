from django.views.generic import TemplateView


class LandingPageView(TemplateView):
    template_name = "index.html"


class BookingPageView(TemplateView):
    template_name = "booking.html"


class MentionsLegalesView(TemplateView):
    template_name = "mentions-legales.html"


class PolitiqueConfidentialiteView(TemplateView):
    template_name = "politique-de-confidentialite.html"


class ContactPageView(TemplateView):
    template_name = "contact.html"


class AnnuaireView(TemplateView):
    template_name = "annuaire.html"


class ReviewPageView(TemplateView):
    template_name = "avis.html"
