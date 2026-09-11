import pytest
from unittest.mock import patch
from datetime import timedelta, datetime, time
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="pastslots@example.com", email="pastslots@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Dupont", specialty="kine",
        booking_page_slug="jean-dupont-pastslots-test",
    )


@pytest.fixture
def owner_client(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


class TestTimeSlotListExcludesPast:
    def test_past_slot_not_returned_in_list(self, db, owner_client, practitioner):
        from apps.appointments.models import TimeSlot

        past = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1),
            is_available=True,
        )
        future = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            is_available=True,
        )
        res = owner_client.get("/api/appointments/timeslots/")
        assert res.status_code == 200
        ids = [s["id"] for s in res.data]
        assert future.id in ids
        assert past.id not in ids


class TestBookManualRejectsPastSlot:
    def test_book_manual_on_past_slot_is_rejected(self, db, owner_client, practitioner):
        from apps.appointments.models import TimeSlot, Appointment

        slot = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() - timedelta(hours=1),
            end_time=timezone.now() - timedelta(minutes=30),
            is_available=True,
        )
        res = owner_client.post("/api/appointments/book_manual/", {
            "timeslot_id": slot.id,
            "patient": {"first_name": "Marie", "last_name": "Martin", "email": "marie.past@example.com"},
        }, format="json")
        assert res.status_code == 409, res.data
        assert not Appointment.objects.filter(patient__email="marie.past@example.com").exists()
        slot.refresh_from_db()
        assert slot.is_available is True


class TestNewRuleGeneratesSlotsImmediately:
    def test_creating_a_rule_for_today_generates_slots_without_waiting_for_the_daily_task(
        self, db, owner_client, practitioner
    ):
        from apps.appointments.models import TimeSlot

        now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        with patch("apps.notifications.tasks.timezone.now", return_value=now):
            res = owner_client.post("/api/appointments/availability-rules/", {
                "practitioner": practitioner.id,
                "weekday": now.weekday(),
                "start_time": "09:00:00",
                "end_time": "18:00:00",
                "slot_duration_minutes": 30,
            }, format="json")
        assert res.status_code == 201, res.data

        assert TimeSlot.objects.filter(
            practitioner=practitioner, start_time__date=now.date()
        ).exists()

    def test_reactivating_a_rule_generates_slots_immediately(self, db, owner_client, practitioner):
        from apps.appointments.models import AvailabilityRule, TimeSlot

        now = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
        rule = AvailabilityRule.objects.create(
            practitioner=practitioner, weekday=now.weekday(),
            start_time=time(9, 0), end_time=time(18, 0), slot_duration_minutes=30,
            is_active=False,
        )
        assert not TimeSlot.objects.filter(practitioner=practitioner).exists()

        with patch("apps.notifications.tasks.timezone.now", return_value=now):
            res = owner_client.patch(f"/api/appointments/availability-rules/{rule.id}/", {
                "is_active": True,
            }, format="json")
        assert res.status_code == 200, res.data

        assert TimeSlot.objects.filter(
            practitioner=practitioner, start_time__date=now.date()
        ).exists()


class TestGenerateSlotsSkipsPastTimesToday:
    def test_todays_rule_does_not_create_a_slot_already_in_the_past(self, db, practitioner):
        from apps.appointments.models import AvailabilityRule, TimeSlot
        from apps.notifications.tasks import generate_slots_from_availability

        # Simule une exécution de la tâche à 15h alors que la règle du jour
        # couvre 9h-18h : les créneaux 9h-15h doivent être ignorés, ceux de
        # 15h-18h doivent être créés.
        now = timezone.now().replace(hour=15, minute=0, second=0, microsecond=0)
        AvailabilityRule.objects.create(
            practitioner=practitioner, weekday=now.weekday(),
            start_time=time(9, 0), end_time=time(18, 0), slot_duration_minutes=60,
        )

        with patch("apps.notifications.tasks.timezone.now", return_value=now):
            generate_slots_from_availability()

        slots = TimeSlot.objects.filter(practitioner=practitioner).order_by("start_time")
        assert slots.exists()
        assert all(s.start_time >= now for s in slots), [s.start_time for s in slots]
        assert not slots.filter(start_time__lt=now).exists()
