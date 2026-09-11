import pytest
from unittest.mock import patch, MagicMock
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="depot@example.com", email="depot@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner_no_deposit(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Dupont", specialty="kine",
        booking_page_slug="jean-dupont-deposit-test",
    )


@pytest.fixture
def practitioner_with_deposit(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Alice", last_name="Martin", specialty="osteo",
        booking_page_slug="alice-martin-deposit-test", deposit_amount_cents=2000,
    )


def make_slot(practitioner):
    from django.utils import timezone
    from datetime import timedelta
    from apps.appointments.models import TimeSlot
    return TimeSlot.objects.create(
        practitioner=practitioner,
        start_time=timezone.now() + timedelta(days=1),
        end_time=timezone.now() + timedelta(days=1, hours=1),
        is_available=True,
    )


class TestBookingPastSlot:
    def test_booking_a_slot_whose_time_has_passed_is_rejected(self, db, practitioner_no_deposit):
        from django.utils import timezone
        from datetime import timedelta
        from apps.appointments.models import TimeSlot

        slot = TimeSlot.objects.create(
            practitioner=practitioner_no_deposit,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            is_available=True,
        )
        client = APIClient()
        res = client.post(
            f"/api/public/book/{practitioner_no_deposit.booking_page_slug}/book/",
            {
                "first_name": "Marie", "last_name": "Martin", "email": "marie@example.com",
                "timeslot_id": slot.id,
            },
            format="json",
        )
        assert res.status_code == 409, res.data

        from apps.appointments.models import Appointment
        assert not Appointment.objects.filter(patient__email="marie@example.com").exists()
        slot.refresh_from_db()
        assert slot.is_available is True


class TestBookingWithoutDeposit:
    def test_booking_confirms_immediately(self, db, practitioner_no_deposit):
        slot = make_slot(practitioner_no_deposit)
        client = APIClient()
        res = client.post(
            f"/api/public/book/{practitioner_no_deposit.booking_page_slug}/book/",
            {
                "first_name": "Marie", "last_name": "Martin", "email": "marie@example.com",
                "timeslot_id": slot.id,
            },
            format="json",
        )
        assert res.status_code == 201, res.data
        assert res.data["requires_payment"] is False

        from apps.appointments.models import Appointment
        appt = Appointment.objects.get(pk=res.data["appointment"]["id"])
        assert appt.status == Appointment.STATUS_CONFIRMED


class TestBookingWithDeposit:
    @patch("stripe.checkout.Session.create")
    def test_booking_creates_pending_appointment_and_checkout_session(self, mock_create, db, practitioner_with_deposit):
        mock_create.return_value = MagicMock(id="cs_test_123", url="https://checkout.stripe.com/test")
        slot = make_slot(practitioner_with_deposit)
        client = APIClient()
        res = client.post(
            f"/api/public/book/{practitioner_with_deposit.booking_page_slug}/book/",
            {
                "first_name": "Paul", "last_name": "Durand", "email": "paul@example.com",
                "timeslot_id": slot.id,
            },
            format="json",
        )
        assert res.status_code == 201, res.data
        assert res.data["requires_payment"] is True
        assert res.data["checkout_url"] == "https://checkout.stripe.com/test"

        from apps.appointments.models import Appointment
        from apps.billing.models import Invoice
        appt = Appointment.objects.get(pk=res.data["appointment"]["id"])
        assert appt.status == Appointment.STATUS_PENDING

        invoice = Invoice.objects.get(appointment=appt)
        assert invoice.amount_cents == 2000
        assert invoice.status == Invoice.STATUS_UNPAID
        assert invoice.stripe_checkout_session_id == "cs_test_123"

        # Le créneau est déjà marqué indisponible pendant l'attente de paiement.
        slot.refresh_from_db()
        assert slot.is_available is False

        # Vérifie que le webhook n'a pas déjà envoyé la confirmation avant paiement.
        mock_create.assert_called_once()
        _, kwargs = mock_create.call_args
        assert kwargs["metadata"]["invoice_id"] == str(invoice.pk)

    @patch("stripe.checkout.Session.create")
    def test_webhook_confirms_appointment_after_deposit_paid(self, mock_create, db, practitioner_with_deposit):
        mock_create.return_value = MagicMock(id="cs_test_456", url="https://checkout.stripe.com/test2")
        slot = make_slot(practitioner_with_deposit)
        client = APIClient()
        res = client.post(
            f"/api/public/book/{practitioner_with_deposit.booking_page_slug}/book/",
            {
                "first_name": "Sophie", "last_name": "Leroux", "email": "sophie@example.com",
                "timeslot_id": slot.id,
            },
            format="json",
        )
        appointment_id = res.data["appointment"]["id"]

        from apps.billing.models import Invoice
        from apps.appointments.models import Appointment
        invoice = Invoice.objects.get(appointment_id=appointment_id)

        with patch("apps.notifications.services.EmailService.send_confirmation") as mock_email:
            from apps.billing.views import StripeWebhookView
            view = StripeWebhookView()
            view._handle_checkout_completed({"metadata": {"invoice_id": str(invoice.pk)}})
            mock_email.assert_called_once()

        invoice.refresh_from_db()
        assert invoice.status == Invoice.STATUS_PAID
        assert invoice.paid_at is not None

        appt = Appointment.objects.get(pk=appointment_id)
        assert appt.status == Appointment.STATUS_CONFIRMED

    def test_deposit_amount_exposed_on_public_practitioner_view(self, db, practitioner_with_deposit):
        client = APIClient()
        res = client.get(f"/api/public/book/{practitioner_with_deposit.booking_page_slug}/")
        assert res.status_code == 200
        assert res.data["practitioner"]["deposit_amount_cents"] == 2000
