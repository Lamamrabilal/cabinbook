from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.billing.views import (
    CreateCheckoutSessionView, StripeWebhookView, CancelSubscriptionView, InvoiceViewSet,
)

router = DefaultRouter()
router.register("invoices", InvoiceViewSet, basename="invoice")

urlpatterns = [
    path("checkout/", CreateCheckoutSessionView.as_view(), name="checkout"),
    path("webhook/", StripeWebhookView.as_view(), name="stripe-webhook"),
    path("cancel/", CancelSubscriptionView.as_view(), name="cancel-subscription"),
    path("", include(router.urls)),
]
