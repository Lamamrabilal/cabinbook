"""Tests de la réservation en langage naturel (l'API Claude est toujours mockée)."""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.utils import timezone
from rest_framework.test import APIClient

from apps.appointments import ai_booking

PARIS = ZoneInfo("Europe/Paris")
LLM = "apps.appointments.ai_booking._call_llm"


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="ai@example.com", email="ai@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Dupont", specialty="kine",
        booking_page_slug="jean-dupont-ai-test",
    )


def make_slot(practitioner, day, hour, available=True):
    """Crée un créneau d'une heure à l'heure de Paris (day = date)."""
    from apps.appointments.models import TimeSlot
    start = datetime(day.year, day.month, day.day, hour, 0, tzinfo=PARIS)
    return TimeSlot.objects.create(
        practitioner=practitioner, start_time=start,
        end_time=start + timedelta(hours=1), is_available=available,
    )


def next_weekday(weekday, min_days=2):
    d = timezone.now().astimezone(PARIS).date() + timedelta(days=min_days)
    while d.weekday() != weekday:
        d += timedelta(days=1)
    return d


def url(practitioner):
    return f"/api/public/book/{practitioner.booking_page_slug}/suggest/"


NONE_PREFS = {"date_from": None, "date_to": None, "weekdays": None, "time_from": None, "time_to": None}


class TestParsePreferences:
    today = date(2026, 11, 10)

    def test_valid_output(self):
        prefs = ai_booking.parse_preferences(
            {**NONE_PREFS, "weekdays": [1], "time_from": "13:00", "time_to": "18:00"}, self.today
        )
        assert prefs.weekdays == [1]
        assert prefs.describe() == "mardi · entre 13:00 et 18:00"

    def test_all_null_is_not_understood(self):
        with pytest.raises(ai_booking.AIBookingNotUnderstood):
            ai_booking.parse_preferences(NONE_PREFS, self.today)

    @pytest.mark.parametrize("bad", [
        {"weekdays": [7]},
        {"weekdays": ["mardi"]},
        {"weekdays": [True]},
        {"time_from": "25:00"},
        {"time_from": "14h"},
        {"date_from": "demain"},
        {"time_from": "18:00", "time_to": "09:00"},
        {"date_from": "2026-12-10", "date_to": "2026-12-01"},
        {"date_to": "2026-01-01"},
    ])
    def test_invalid_llm_output_is_rejected(self, bad):
        with pytest.raises(ai_booking.AIBookingError):
            ai_booking.parse_preferences({**NONE_PREFS, **bad}, self.today)

    def test_non_dict_output_is_rejected(self):
        with pytest.raises(ai_booking.AIBookingError):
            ai_booking.parse_preferences("n'importe quoi", self.today)

    def test_past_start_date_is_clamped_to_today(self):
        prefs = ai_booking.parse_preferences({**NONE_PREFS, "date_from": "2026-01-01"}, self.today)
        assert prefs.date_from == self.today


class TestSuggestEndpoint:
    def test_returns_only_matching_real_slots(self, practitioner):
        tuesday = next_weekday(1)
        wednesday = tuesday + timedelta(days=1)
        match = make_slot(practitioner, tuesday, 14)
        make_slot(practitioner, tuesday, 9)       # mauvais horaire
        make_slot(practitioner, wednesday, 14)    # mauvais jour
        make_slot(practitioner, tuesday, 15, available=False)  # déjà réservé

        with patch(LLM, return_value={**NONE_PREFS, "weekdays": [1], "time_from": "13:00", "time_to": "18:00"}):
            res = APIClient().post(url(practitioner), {"message": "un rdv mardi après-midi"}, format="json")

        assert res.status_code == 200
        assert [s["id"] for s in res.data["slots"]] == [match.id]
        assert res.data["interpreted"] == "mardi · entre 13:00 et 18:00"

    def test_other_practitioner_slots_never_leak(self, practitioner, django_user_model):
        from apps.accounts.models import Practitioner
        other_owner = django_user_model.objects.create_user(
            username="other-ai@example.com", email="other-ai@example.com",
            password="x", plan="pro", is_subscription_active=True,
        )
        other = Practitioner.objects.create(
            owner=other_owner, first_name="Marie", last_name="Martin", specialty="osteo",
            booking_page_slug="marie-martin-ai-test",
        )
        tuesday = next_weekday(1)
        make_slot(other, tuesday, 14)

        with patch(LLM, return_value={**NONE_PREFS, "weekdays": [1]}):
            res = APIClient().post(url(practitioner), {"message": "mardi"}, format="json")

        assert res.status_code == 200
        assert res.data["slots"] == []

    def test_past_slots_are_never_suggested(self, practitioner):
        from apps.appointments.models import TimeSlot
        TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() - timedelta(days=1),
            end_time=timezone.now() - timedelta(days=1) + timedelta(hours=1),
            is_available=True,
        )
        with patch(LLM, return_value={**NONE_PREFS, "time_from": "00:00", "time_to": "23:59"}):
            res = APIClient().post(url(practitioner), {"message": "n'importe quand"}, format="json")
        assert res.status_code == 200
        assert res.data["slots"] == []

    def test_message_not_understood_returns_422(self, practitioner):
        with patch(LLM, return_value=NONE_PREFS):
            res = APIClient().post(url(practitioner), {"message": "bonjour"}, format="json")
        assert res.status_code == 422

    def test_llm_failure_returns_502(self, practitioner):
        with patch(LLM, side_effect=ai_booking.AIBookingError("boom")):
            res = APIClient().post(url(practitioner), {"message": "mardi"}, format="json")
        assert res.status_code == 502

    def test_garbage_llm_output_returns_502(self, practitioner):
        with patch(LLM, return_value={**NONE_PREFS, "weekdays": [42]}):
            res = APIClient().post(url(practitioner), {"message": "mardi"}, format="json")
        assert res.status_code == 502

    def test_disabled_without_api_key_returns_503(self, practitioner, settings):
        settings.ANTHROPIC_API_KEY = ""
        res = APIClient().post(url(practitioner), {"message": "mardi"}, format="json")
        assert res.status_code == 503

    @pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "ab"}, {"message": "x" * 301}])
    def test_invalid_message_returns_400(self, practitioner, payload):
        with patch(LLM) as llm:
            res = APIClient().post(url(practitioner), payload, format="json")
        assert res.status_code == 400
        llm.assert_not_called()

    def test_inactive_subscription_returns_503_without_llm_call(self, practitioner, owner):
        owner.is_subscription_active = False
        owner.save()
        with patch(LLM) as llm:
            res = APIClient().post(url(practitioner), {"message": "mardi"}, format="json")
        assert res.status_code == 503
        llm.assert_not_called()

    def test_unknown_practitioner_returns_404(self, db):
        res = APIClient().post("/api/public/book/inconnu/suggest/", {"message": "mardi"}, format="json")
        assert res.status_code == 404

    def test_rate_limited_after_10_requests(self, practitioner):
        client = APIClient()
        with patch(LLM, return_value={**NONE_PREFS, "weekdays": [1]}):
            codes = [client.post(url(practitioner), {"message": "mardi"}, format="json").status_code for _ in range(11)]
        assert codes[:10] == [200] * 10
        assert codes[10] == 429
