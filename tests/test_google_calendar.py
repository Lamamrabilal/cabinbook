import pytest
from unittest.mock import patch, MagicMock
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="gcal@example.com", email="gcal@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Dupont", specialty="kine",
        booking_page_slug="jean-dupont-gcal-test",
    )


@pytest.fixture
def patient(db, practitioner):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner, first_name="Marie", last_name="Martin",
        email="marie.gcal@example.com",
    )


@pytest.fixture
def owner_client(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


@pytest.fixture
def connection(db, practitioner):
    from apps.accounts.models import GoogleCalendarConnection
    return GoogleCalendarConnection.objects.create(
        practitioner=practitioner, google_email="jean@gmail.com",
        access_token="fake-access-token", refresh_token="fake-refresh-token",
        token_expiry=timezone.now() + timedelta(hours=1),
    )


class TestGoogleCalendarConnect:
    def test_connect_returns_authorization_url_for_owned_practitioner(self, owner_client, practitioner):
        res = owner_client.get(f"/api/accounts/calendar/google/connect/?practitioner={practitioner.id}")
        assert res.status_code == 200
        assert "accounts.google.com" in res.data["authorization_url"]
        assert "state=" in res.data["authorization_url"]

    def test_connect_rejects_practitioner_not_owned(self, db, owner_client, django_user_model):
        from apps.accounts.models import Practitioner
        other_owner = django_user_model.objects.create_user(
            username="other-gcal@example.com", email="other-gcal@example.com", password="testpass123",
        )
        other_practitioner = Practitioner.objects.create(
            owner=other_owner, first_name="Bob", last_name="B", specialty="osteo",
            booking_page_slug="bob-b-gcal-test",
        )
        res = owner_client.get(f"/api/accounts/calendar/google/connect/?practitioner={other_practitioner.id}")
        assert res.status_code == 404


class TestGoogleCalendarCallback:
    def test_callback_creates_connection_and_redirects_to_success(self, db, practitioner):
        from apps.accounts import google_calendar
        from apps.accounts.models import GoogleCalendarConnection

        state = google_calendar.build_authorization_url(practitioner).split("state=")[1]
        client = APIClient()
        with patch(
            "apps.accounts.google_calendar.exchange_code_for_tokens",
            return_value={"access_token": "tok", "refresh_token": "reftok", "expires_in": 3600},
        ), patch("apps.accounts.google_calendar.fetch_google_email", return_value="jean@gmail.com"):
            res = client.get(f"/api/accounts/calendar/google/callback/?code=abc&state={state}")

        assert res.status_code == 302
        assert "calendar=connected" in res.url

        connection = GoogleCalendarConnection.objects.get(practitioner=practitioner)
        assert connection.google_email == "jean@gmail.com"
        assert connection.refresh_token == "reftok"

    def test_callback_redirects_to_error_on_missing_code(self, db):
        client = APIClient()
        res = client.get("/api/accounts/calendar/google/callback/?state=whatever")
        assert res.status_code == 302
        assert "calendar=error" in res.url

    def test_callback_redirects_to_error_on_invalid_state(self, db):
        client = APIClient()
        res = client.get("/api/accounts/calendar/google/callback/?code=abc&state=not-a-valid-signed-state")
        assert res.status_code == 302
        assert "calendar=error" in res.url


class TestGoogleCalendarDisconnect:
    def test_disconnect_removes_connection(self, owner_client, practitioner, connection):
        from apps.accounts.models import GoogleCalendarConnection
        with patch("apps.accounts.google_calendar.revoke"):
            res = owner_client.post(
                "/api/accounts/calendar/google/disconnect/", {"practitioner": practitioner.id}, format="json"
            )
        assert res.status_code == 200
        assert not GoogleCalendarConnection.objects.filter(practitioner=practitioner).exists()

    def test_disconnect_without_connection_returns_404(self, owner_client, practitioner):
        res = owner_client.post(
            "/api/accounts/calendar/google/disconnect/", {"practitioner": practitioner.id}, format="json"
        )
        assert res.status_code == 404


class TestAppointmentSyncSignal:
    def test_saving_appointment_triggers_sync_when_practitioner_connected(
        self, db, practitioner, patient, connection
    ):
        from apps.appointments.models import Appointment

        with patch("apps.notifications.tasks.sync_appointment_to_google.delay") as mock_delay:
            appt = Appointment.objects.create(
                practitioner=practitioner, patient=patient,
                start_time=timezone.now() + timedelta(days=1),
                end_time=timezone.now() + timedelta(days=1, hours=1),
            )
        mock_delay.assert_called_once_with(appt.pk)

    def test_saving_appointment_does_not_trigger_sync_when_not_connected(self, db, practitioner, patient):
        from apps.appointments.models import Appointment

        with patch("apps.notifications.tasks.sync_appointment_to_google.delay") as mock_delay:
            Appointment.objects.create(
                practitioner=practitioner, patient=patient,
                start_time=timezone.now() + timedelta(days=1),
                end_time=timezone.now() + timedelta(days=1, hours=1),
            )
        mock_delay.assert_not_called()


class TestSyncAppointmentToGoogleTask:
    def test_confirmed_appointment_creates_google_event(self, db, practitioner, patient, connection):
        from apps.appointments.models import Appointment
        from apps.notifications.tasks import sync_appointment_to_google

        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CONFIRMED,
        )
        with patch("apps.accounts.google_calendar.upsert_event", return_value="google-evt-123") as mock_upsert:
            sync_appointment_to_google(appt.pk)

        mock_upsert.assert_called_once()
        appt.refresh_from_db()
        assert appt.google_event_id == "google-evt-123"

    def test_cancelled_appointment_deletes_google_event(self, db, practitioner, patient, connection):
        from apps.appointments.models import Appointment
        from apps.notifications.tasks import sync_appointment_to_google

        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CANCELLED,
            google_event_id="google-evt-456",
        )
        with patch("apps.accounts.google_calendar.delete_event") as mock_delete:
            sync_appointment_to_google(appt.pk)

        mock_delete.assert_called_once()
        appt.refresh_from_db()
        assert appt.google_event_id == ""

    def test_no_connection_does_nothing(self, db, practitioner, patient):
        from apps.appointments.models import Appointment
        from apps.notifications.tasks import sync_appointment_to_google

        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CONFIRMED,
        )
        with patch("apps.accounts.google_calendar.upsert_event") as mock_upsert:
            sync_appointment_to_google(appt.pk)
        mock_upsert.assert_not_called()


class TestSyncBusyPeriodsFromGoogleTask:
    def test_overlapping_busy_period_blocks_available_slot(self, db, practitioner, connection):
        from apps.appointments.models import TimeSlot
        from apps.notifications.tasks import sync_busy_periods_from_google

        start = timezone.now() + timedelta(hours=2)
        slot = TimeSlot.objects.create(
            practitioner=practitioner, start_time=start, end_time=start + timedelta(hours=1),
            is_available=True,
        )
        busy = [{"start": start.isoformat(), "end": (start + timedelta(hours=1)).isoformat()}]
        with patch("apps.accounts.google_calendar.get_busy_periods", return_value=busy):
            sync_busy_periods_from_google()

        slot.refresh_from_db()
        assert slot.is_available is False
        assert slot.blocked_by_external_calendar is True

    def test_slot_released_when_no_longer_busy(self, db, practitioner, connection):
        from apps.appointments.models import TimeSlot
        from apps.notifications.tasks import sync_busy_periods_from_google

        start = timezone.now() + timedelta(hours=2)
        slot = TimeSlot.objects.create(
            practitioner=practitioner, start_time=start, end_time=start + timedelta(hours=1),
            is_available=False, blocked_by_external_calendar=True,
        )
        with patch("apps.accounts.google_calendar.get_busy_periods", return_value=[]):
            sync_busy_periods_from_google()

        slot.refresh_from_db()
        assert slot.is_available is True
        assert slot.blocked_by_external_calendar is False

    def test_real_booking_not_touched_even_if_also_busy_on_google(self, db, practitioner, patient, connection):
        """Un créneau déjà pris par un vrai RDV CabinBook ne doit jamais être
        marqué blocked_by_external_calendar, même s'il apparaît aussi occupé
        côté Google (c'est justement l'événement qu'on y a nous-mêmes poussé)."""
        from apps.appointments.models import TimeSlot
        from apps.notifications.tasks import sync_busy_periods_from_google

        start = timezone.now() + timedelta(hours=2)
        slot = TimeSlot.objects.create(
            practitioner=practitioner, start_time=start, end_time=start + timedelta(hours=1),
            is_available=False,
        )
        busy = [{"start": start.isoformat(), "end": (start + timedelta(hours=1)).isoformat()}]
        with patch("apps.accounts.google_calendar.get_busy_periods", return_value=busy):
            sync_busy_periods_from_google()

        slot.refresh_from_db()
        assert slot.is_available is False
        assert slot.blocked_by_external_calendar is False
