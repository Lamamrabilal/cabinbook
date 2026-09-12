"""
Couverture des flux de facturation : accès des comptes secrétaire aux
factures (facturation front-desk), et gestion des cas d'erreur (facture en
double sur un même RDV).
"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="billing-owner@example.com", email="billing-owner@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Dupont", specialty="kine",
        booking_page_slug="jean-dupont-billing-test",
    )


@pytest.fixture
def patient(db, practitioner):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner, first_name="Marie", last_name="Martin",
        email="marie.billing@example.com",
    )


@pytest.fixture
def appointment(db, practitioner, patient):
    from apps.appointments.models import Appointment
    return Appointment.objects.create(
        practitioner=practitioner, patient=patient,
        start_time=timezone.now() - timedelta(hours=1),
        end_time=timezone.now(),
        status=Appointment.STATUS_DONE,
    )


@pytest.fixture
def secretary(db, owner):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="secretary-billing@example.com", email="secretary-billing@example.com",
        password="testpass123", role=User.ROLE_SECRETARY, owner_account=owner,
    )


@pytest.fixture
def owner_client(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


@pytest.fixture
def secretary_client(secretary):
    c = APIClient()
    c.force_authenticate(user=secretary)
    return c


class TestSecretaryCanCreateInvoices:
    """La doc de InvoiceViewSet dit explicitement que la facturation front-desk
    doit être accessible aux comptes secrétaire — à vérifier concrètement."""

    def test_secretary_can_create_an_invoice_for_owners_appointment(self, secretary_client, appointment):
        res = secretary_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        assert res.status_code == 201, res.data

    def test_owner_can_still_create_an_invoice(self, owner_client, appointment):
        res = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        assert res.status_code == 201, res.data


class TestEditInvoiceAmount:
    def test_owner_can_edit_amount_on_unpaid_invoice(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        res = owner_client.patch(f"/api/billing/invoices/{created.data['id']}/", {
            "amount_cents": 5000,
        }, format="json")
        assert res.status_code == 200, res.data
        assert res.data["amount_cents"] == 5000

    def test_amount_cannot_be_changed_once_paid(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        invoice_id = created.data["id"]
        mark_paid_res = owner_client.post(f"/api/billing/invoices/{invoice_id}/mark_paid/")
        assert mark_paid_res.status_code == 200

        res = owner_client.patch(f"/api/billing/invoices/{invoice_id}/", {
            "amount_cents": 9999,
        }, format="json")
        assert res.status_code == 400, res.data

        from apps.billing.models import Invoice
        assert Invoice.objects.get(pk=invoice_id).amount_cents == 4500


class TestRefundInvoice:
    def test_cannot_refund_an_unpaid_invoice(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        res = owner_client.post(f"/api/billing/invoices/{created.data['id']}/refund/")
        assert res.status_code == 400, res.data

    def test_refunding_a_manually_paid_invoice_does_not_call_stripe(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        invoice_id = created.data["id"]
        owner_client.post(f"/api/billing/invoices/{invoice_id}/mark_paid/")

        with patch("stripe.Refund.create") as mock_refund:
            res = owner_client.post(f"/api/billing/invoices/{invoice_id}/refund/")
        assert res.status_code == 200, res.data
        assert res.data["status"] == "refunded"
        mock_refund.assert_not_called()

    def test_refunding_a_stripe_paid_invoice_calls_stripe_refund(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        invoice_id = created.data["id"]

        from apps.billing.models import Invoice
        invoice = Invoice.objects.get(pk=invoice_id)
        invoice.status = Invoice.STATUS_PAID
        invoice.stripe_checkout_session_id = "cs_test_refund_123"
        invoice.save(update_fields=["status", "stripe_checkout_session_id"])

        with patch("stripe.checkout.Session.retrieve", return_value={"payment_intent": "pi_test_123"}), \
             patch("stripe.Refund.create") as mock_refund:
            res = owner_client.post(f"/api/billing/invoices/{invoice_id}/refund/")

        assert res.status_code == 200, res.data
        assert res.data["status"] == "refunded"
        mock_refund.assert_called_once_with(payment_intent="pi_test_123")

    def test_cannot_refund_twice(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        invoice_id = created.data["id"]
        owner_client.post(f"/api/billing/invoices/{invoice_id}/mark_paid/")
        owner_client.post(f"/api/billing/invoices/{invoice_id}/refund/")

        res = owner_client.post(f"/api/billing/invoices/{invoice_id}/refund/")
        assert res.status_code == 400, res.data

    def test_cannot_mark_a_refunded_invoice_paid_again(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        invoice_id = created.data["id"]
        owner_client.post(f"/api/billing/invoices/{invoice_id}/mark_paid/")
        owner_client.post(f"/api/billing/invoices/{invoice_id}/refund/")

        res = owner_client.post(f"/api/billing/invoices/{invoice_id}/mark_paid/")
        assert res.status_code == 400, res.data

    def test_amount_cannot_be_changed_once_refunded(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        invoice_id = created.data["id"]
        owner_client.post(f"/api/billing/invoices/{invoice_id}/mark_paid/")
        owner_client.post(f"/api/billing/invoices/{invoice_id}/refund/")

        res = owner_client.patch(f"/api/billing/invoices/{invoice_id}/", {"amount_cents": 9999}, format="json")
        assert res.status_code == 400, res.data


class TestDuplicateInvoiceOnSameAppointment:
    def test_creating_a_second_invoice_for_the_same_appointment_is_rejected_cleanly(
        self, owner_client, appointment
    ):
        first = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        assert first.status_code == 201, first.data

        second = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        assert second.status_code == 400, second.data


class TestInvoiceListView:
    """Vue de facturation centralisée (liste de toutes les factures du cabinet)."""

    def test_list_includes_patient_and_practitioner_names(self, owner_client, appointment):
        owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")

        res = owner_client.get("/api/billing/invoices/")
        assert res.status_code == 200, res.data
        assert len(res.data) == 1
        assert res.data[0]["patient_name"] == "Marie Martin"
        assert res.data[0]["practitioner_name"] == str(appointment.practitioner)

    def test_filter_by_status(self, owner_client, appointment):
        created = owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json").data
        owner_client.post(f"/api/billing/invoices/{created['id']}/mark_paid/")

        unpaid = owner_client.get("/api/billing/invoices/?status=unpaid")
        assert unpaid.data == []

        paid = owner_client.get("/api/billing/invoices/?status=paid")
        assert len(paid.data) == 1
        assert paid.data[0]["id"] == created["id"]

    def test_filter_by_practitioner(self, owner_client, owner, appointment):
        from apps.accounts.models import Practitioner, Patient
        from apps.appointments.models import Appointment

        other_practitioner = Practitioner.objects.create(
            owner=owner, first_name="Sophie", last_name="Bernard", specialty="osteo",
            booking_page_slug="sophie-bernard-billing-test",
        )
        other_patient = Patient.objects.create(
            practitioner=other_practitioner, first_name="Léo", last_name="Petit",
            email="leo@example.com",
        )
        other_appointment = Appointment.objects.create(
            practitioner=other_practitioner, patient=other_patient,
            start_time=timezone.now() - timedelta(hours=1), end_time=timezone.now(),
            status=Appointment.STATUS_DONE,
        )
        owner_client.post("/api/billing/invoices/", {
            "appointment": appointment.id, "amount_cents": 4500,
        }, format="json")
        owner_client.post("/api/billing/invoices/", {
            "appointment": other_appointment.id, "amount_cents": 3000,
        }, format="json")

        res = owner_client.get(f"/api/billing/invoices/?practitioner={other_practitioner.id}")
        assert len(res.data) == 1
        assert res.data[0]["practitioner_name"] == str(other_practitioner)

    def test_invoices_from_another_tenant_are_not_listed(self, owner_client, django_user_model):
        from apps.accounts.models import Practitioner, Patient
        from apps.appointments.models import Appointment

        other_owner = django_user_model.objects.create_user(
            username="other-billing-owner@example.com", email="other-billing-owner@example.com",
            password="testpass123", plan="pro", is_subscription_active=True,
        )
        other_practitioner = Practitioner.objects.create(
            owner=other_owner, first_name="Alex", last_name="Roux", specialty="psy",
            booking_page_slug="alex-roux-billing-test",
        )
        other_patient = Patient.objects.create(
            practitioner=other_practitioner, first_name="Nina", last_name="Simon",
            email="nina@example.com",
        )
        other_appointment = Appointment.objects.create(
            practitioner=other_practitioner, patient=other_patient,
            start_time=timezone.now() - timedelta(hours=1), end_time=timezone.now(),
            status=Appointment.STATUS_DONE,
        )
        from apps.billing.models import Invoice
        Invoice.objects.create(appointment=other_appointment, amount_cents=5000)

        res = owner_client.get("/api/billing/invoices/")
        assert res.data == []
