import pytest
from rest_framework.test import APIClient


@pytest.fixture
def cabinet_owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="cabinet@example.com", email="cabinet@example.com",
        password="testpass123", plan="cabinet", is_subscription_active=True,
    )


@pytest.fixture
def pro_owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="solo@example.com", email="solo@example.com",
        password="testpass123", plan="pro",
    )


@pytest.fixture
def practitioner_a(db, cabinet_owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=cabinet_owner, first_name="Alice", last_name="A", specialty="kine",
        booking_page_slug="alice-a-room-test",
    )


@pytest.fixture
def practitioner_b(db, cabinet_owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=cabinet_owner, first_name="Bob", last_name="B", specialty="osteo",
        booking_page_slug="bob-b-room-test",
    )


@pytest.fixture
def cabinet_client(cabinet_owner):
    c = APIClient()
    c.force_authenticate(user=cabinet_owner)
    return c


def make_patient(practitioner, suffix):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner, first_name="Pat", last_name=suffix,
        email=f"pat-{suffix}@example.com",
    )


class TestRoomManagement:
    def test_cabinet_owner_can_create_room(self, cabinet_client):
        res = cabinet_client.post("/api/accounts/rooms/", {"name": "Salle 1"})
        assert res.status_code == 201, res.data

    def test_pro_plan_cannot_create_rooms(self, pro_owner):
        client = APIClient()
        client.force_authenticate(user=pro_owner)
        res = client.post("/api/accounts/rooms/", {"name": "Salle 1"})
        assert res.status_code == 403

    def test_duplicate_room_name_rejected(self, cabinet_client):
        cabinet_client.post("/api/accounts/rooms/", {"name": "Salle 1"})
        res = cabinet_client.post("/api/accounts/rooms/", {"name": "Salle 1"})
        assert res.status_code == 400

    def test_secretary_cannot_manage_rooms(self, cabinet_client, cabinet_owner):
        from apps.accounts.models import User
        secretary = User.objects.create_user(
            username="sec-room@example.com", email="sec-room@example.com",
            password="testpass123", role=User.ROLE_SECRETARY, owner_account=cabinet_owner,
        )
        client = APIClient()
        client.force_authenticate(user=secretary)
        res = client.post("/api/accounts/rooms/", {"name": "Salle 2"})
        assert res.status_code == 403

    def test_secretary_can_list_rooms_to_assign_them(self, cabinet_client, cabinet_owner):
        from apps.accounts.models import User, Room
        Room.objects.create(owner=cabinet_owner, name="Salle Front Desk")
        secretary = User.objects.create_user(
            username="sec-room2@example.com", email="sec-room2@example.com",
            password="testpass123", role=User.ROLE_SECRETARY, owner_account=cabinet_owner,
        )
        client = APIClient()
        client.force_authenticate(user=secretary)
        res = client.get("/api/accounts/rooms/")
        assert res.status_code == 200
        assert len(res.data) == 1


class TestRoomBookingConflict:
    def test_room_double_booking_prevented_across_practitioners(
        self, db, cabinet_client, cabinet_owner, practitioner_a, practitioner_b
    ):
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import Room

        room = Room.objects.create(owner=cabinet_owner, name="Salle Unique")
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        patient_a = make_patient(practitioner_a, "a")
        patient_b = make_patient(practitioner_b, "b")

        res1 = cabinet_client.post("/api/appointments/", {
            "practitioner": practitioner_a.id, "patient_id": patient_a.id,
            "start_time": start.isoformat(), "end_time": end.isoformat(),
            "room": room.id,
        }, format="json")
        assert res1.status_code == 201, res1.data

        # Meme salle, meme creneau, AUTRE praticien -> doit echouer malgre l'absence
        # de conflit sur le praticien lui-meme.
        res2 = cabinet_client.post("/api/appointments/", {
            "practitioner": practitioner_b.id, "patient_id": patient_b.id,
            "start_time": start.isoformat(), "end_time": end.isoformat(),
            "room": room.id,
        }, format="json")
        assert res2.status_code == 400
        assert "salle" in str(res2.data).lower()

    def test_room_from_another_cabinet_rejected(
        self, db, cabinet_client, practitioner_a, django_user_model
    ):
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import Room

        other_owner = django_user_model.objects.create_user(
            username="othercabinet@example.com", email="othercabinet@example.com",
            password="testpass123", plan="cabinet",
        )
        other_room = Room.objects.create(owner=other_owner, name="Salle Externe")
        start = timezone.now() + timedelta(days=1)
        end = start + timedelta(hours=1)
        patient = make_patient(practitioner_a, "x")

        res = cabinet_client.post("/api/appointments/", {
            "practitioner": practitioner_a.id, "patient_id": patient.id,
            "start_time": start.isoformat(), "end_time": end.isoformat(),
            "room": other_room.id,
        }, format="json")
        assert res.status_code == 400

    def test_book_manual_with_room(self, db, cabinet_client, cabinet_owner, practitioner_a):
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import Room
        from apps.appointments.models import TimeSlot

        room = Room.objects.create(owner=cabinet_owner, name="Salle Manuelle")
        slot = TimeSlot.objects.create(
            practitioner=practitioner_a,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            is_available=True,
        )
        res = cabinet_client.post("/api/appointments/book_manual/", {
            "timeslot_id": slot.id, "room_id": room.id,
            "patient": {"first_name": "Marie", "last_name": "Martin", "email": "marie.room@example.com"},
        }, format="json")
        assert res.status_code == 201, res.data
        assert res.data["room"] == room.id
