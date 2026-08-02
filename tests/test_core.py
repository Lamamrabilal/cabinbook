import pytest
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="praticien1",
        email="kine@example.com",
        password="testpass123",
        is_subscription_active=True,
        plan="pro",
    )


@pytest.fixture
def practitioner(db, user):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=user,
        first_name="Jean",
        last_name="Dupont",
        specialty="kine",
        booking_page_slug="jean-dupont",
    )


@pytest.fixture
def patient(db, practitioner):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner,
        first_name="Marie",
        last_name="Martin",
        email="marie@example.com",
        phone="+33612345678",
    )


@pytest.fixture
def appointment(db, practitioner, patient):
    from apps.appointments.models import Appointment
    return Appointment.objects.create(
        practitioner=practitioner,
        patient=patient,
        start_time=timezone.now() + timedelta(days=1),
        end_time=timezone.now() + timedelta(days=1, hours=1),
        status=Appointment.STATUS_CONFIRMED,
    )


class TestAppointmentModel:
    def test_tokens_auto_generated(self, appointment):
        assert appointment.confirmation_token
        assert appointment.cancellation_token
        assert len(appointment.confirmation_token) > 20

    def test_str_representation(self, appointment):
        assert "Martin" in str(appointment)
        assert "Dupont" in str(appointment)


class TestReminderTasks:
    @patch("apps.notifications.services.EmailService.send_reminder")
    def test_email_reminder_sent(self, mock_email, appointment):
        from apps.notifications.tasks import send_appointment_reminder_email
        send_appointment_reminder_email(appointment.pk)
        mock_email.assert_called_once_with(appointment)

        appointment.refresh_from_db()
        assert appointment.reminder_email_sent is True

    @patch("apps.notifications.services.SmsService.send_reminder")
    def test_sms_reminder_sent_pro_plan(self, mock_sms, appointment):
        from apps.notifications.tasks import send_appointment_reminder_sms
        send_appointment_reminder_sms(appointment.pk)
        mock_sms.assert_called_once()

    @patch("apps.notifications.services.SmsService.send_reminder")
    def test_sms_skipped_starter_plan(self, mock_sms, appointment, user):
        user.plan = "starter"
        user.save()
        from apps.notifications.tasks import send_appointment_reminder_sms
        send_appointment_reminder_sms(appointment.pk)
        mock_sms.assert_not_called()


class TestBillingWebhook:
    def test_checkout_completed_activates_subscription(self, db, client, user):
        from apps.accounts.models import User
        user.is_subscription_active = False
        user.save()

        # Simuler le handler directement
        from apps.billing.views import StripeWebhookView
        view = StripeWebhookView()
        session = {
            "metadata": {"user_id": str(user.pk), "plan": "pro"},
            "subscription": "sub_test123",
        }
        view._handle_checkout_completed(session)

        user.refresh_from_db()
        assert user.is_subscription_active is True
        assert user.plan == "pro"
        assert user.stripe_subscription_id == "sub_test123"
