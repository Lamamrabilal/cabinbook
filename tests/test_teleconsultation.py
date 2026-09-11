import pytest
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="video@example.com", email="video@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner_video(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Alice", last_name="Psy", specialty="psy",
        booking_page_slug="alice-psy-video-test", offers_teleconsultation=True,
    )


@pytest.fixture
def practitioner_no_video(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Kine", specialty="kine",
        booking_page_slug="jean-kine-video-test", offers_teleconsultation=False,
    )


def make_appointment(practitioner, owner):
    from django.utils import timezone
    from datetime import timedelta
    from apps.accounts.models import Patient
    from apps.appointments.models import Appointment
    patient = Patient.objects.create(
        practitioner=practitioner, first_name="Marie", last_name="Martin",
        email=f"marie-{practitioner.id}@example.com",
    )
    return Appointment.objects.create(
        practitioner=practitioner, patient=patient,
        start_time=timezone.now() + timedelta(days=1),
        end_time=timezone.now() + timedelta(days=1, hours=1),
        status=Appointment.STATUS_CONFIRMED,
    )


class TestVideoRoomUrl:
    def test_video_url_present_when_enabled(self, db, practitioner_video, owner):
        appt = make_appointment(practitioner_video, owner)
        assert appt.video_room_url.startswith("https://meet.jit.si/CabinBook-")
        assert appt.confirmation_token[:24] in appt.video_room_url

    def test_video_url_empty_when_disabled(self, db, practitioner_no_video, owner):
        appt = make_appointment(practitioner_no_video, owner)
        assert appt.video_room_url == ""

    def test_video_url_exposed_in_authenticated_api(self, db, practitioner_video, owner):
        appt = make_appointment(practitioner_video, owner)
        client = APIClient()
        client.force_authenticate(user=owner)
        res = client.get("/api/appointments/")
        assert res.status_code == 200
        rows = res.data["results"] if isinstance(res.data, dict) else res.data
        row = next(r for r in rows if r["id"] == appt.id)
        assert row["video_room_url"] == appt.video_room_url

    def test_video_url_exposed_in_public_booking_response(self, db, practitioner_video):
        from django.utils import timezone
        from datetime import timedelta
        from apps.appointments.models import TimeSlot

        slot = TimeSlot.objects.create(
            practitioner=practitioner_video,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            is_available=True,
        )
        client = APIClient()
        res = client.post(
            f"/api/public/book/{practitioner_video.booking_page_slug}/book/",
            {"first_name": "Paul", "last_name": "Durand", "email": "paul.video@example.com", "timeslot_id": slot.id},
            format="json",
        )
        assert res.status_code == 201, res.data
        assert res.data["appointment"]["video_room_url"].startswith("https://meet.jit.si/")
