from django.urls import path
from apps.billing.views import CreateCheckoutSessionView, StripeWebhookView

urlpatterns = [
    path("checkout/", CreateCheckoutSessionView.as_view(), name="checkout"),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
]
