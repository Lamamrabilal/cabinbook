"""
L'agenda (liste des RDV) est l'écran le plus consulté de l'app. Le queryset
ne préchargeait ni `room` ni `session_note` (accédés dans
AppointmentListSerializer), ce qui déclenchait 2 requêtes SQL supplémentaires
par RDV affiché — avec 500 RDV sur un mois, ça fait ~1000 requêtes en trop.
Ce test garantit que le nombre de requêtes reste constant quel que soit le
nombre de RDV listés.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="perf@example.com", email="perf@example.com",
        password="testpass123", plan="cabinet", is_subscription_active=True,
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Perf", last_name="Test", specialty="kine",
        booking_page_slug="perf-test-practitioner",
    )


@pytest.fixture
def patient(db, practitioner):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner, first_name="P", last_name="Q", email="pq@example.com",
    )


@pytest.fixture
def api_client(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


def _create_appointments(practitioner, patient, room, count):
    from apps.appointments.models import Appointment, SessionNote

    for i in range(count):
        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient, room=room,
            start_time=timezone.now() + timedelta(days=1, hours=i),
            end_time=timezone.now() + timedelta(days=1, hours=i + 1),
        )
        SessionNote.objects.create(appointment=appt, content="note")


class TestAppointmentListQueryCount:
    def test_query_count_does_not_scale_with_number_of_appointments(
        self, api_client, practitioner, patient, django_assert_max_num_queries
    ):
        from apps.accounts.models import Room

        room = Room.objects.create(owner=practitioner.owner, name="Salle 1")
        _create_appointments(practitioner, patient, room, 3)

        # Un premier appel "chauffe" pour mesurer le nombre de requêtes fixe
        # (indépendant du nombre de RDV), puis on vérifie qu'il ne grandit pas
        # avec 10x plus de RDV.
        with django_assert_max_num_queries(10) as small:
            res = api_client.get("/api/appointments/")
        assert res.status_code == 200
        assert len(res.data) == 3

        _create_appointments(practitioner, patient, room, 27)  # total 30

        with django_assert_max_num_queries(len(small.captured_queries)):
            res = api_client.get("/api/appointments/")
        assert res.status_code == 200
        assert len(res.data) == 30
