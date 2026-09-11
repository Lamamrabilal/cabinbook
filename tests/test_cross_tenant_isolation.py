"""
Faille de cloisonnement inter-comptes : plusieurs serializers exposaient un
champ `practitioner` inscriptible sans jamais vérifier qu'il appartient bien
au compte de l'utilisateur connecté. En pratique, un titulaire pouvait — via
un simple POST ou PATCH — créer ou réassigner un RDV, un patient, une série
récurrente, un créneau, une entrée de liste d'attente ou une règle de
disponibilité à un praticien appartenant à un AUTRE compte, faisant fuiter
ses propres données (patient, notes, motif de consultation) dans la
patientèle/l'agenda d'un tiers, ou polluant son agenda.
"""
import pytest
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient


@pytest.fixture
def owner_a(db, django_user_model):
    return django_user_model.objects.create_user(
        username="tenant-a@example.com", email="tenant-a@example.com",
        password="testpass123", plan="cabinet", is_subscription_active=True,
    )


@pytest.fixture
def owner_b(db, django_user_model):
    return django_user_model.objects.create_user(
        username="tenant-b@example.com", email="tenant-b@example.com",
        password="testpass123", plan="cabinet", is_subscription_active=True,
    )


@pytest.fixture
def practitioner_a(db, owner_a):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner_a, first_name="A", last_name="Tenant", specialty="kine",
        booking_page_slug="tenant-a-practitioner",
    )


@pytest.fixture
def practitioner_b(db, owner_b):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner_b, first_name="B", last_name="Tenant", specialty="osteo",
        booking_page_slug="tenant-b-practitioner",
    )


@pytest.fixture
def patient_a(db, practitioner_a):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner_a, first_name="Pat", last_name="A",
        email="pat-a@example.com", carte_vitale_number="123456789012345",
    )


@pytest.fixture
def client_a(owner_a):
    c = APIClient()
    c.force_authenticate(user=owner_a)
    return c


class TestPatientCrossTenantIsolation:
    def test_cannot_create_patient_under_another_tenants_practitioner(self, client_a, practitioner_b):
        res = client_a.post("/api/accounts/patients/", {
            "practitioner": practitioner_b.id, "first_name": "Evil", "last_name": "Injection",
            "email": "evil@example.com",
        }, format="json")
        assert res.status_code == 400, res.data

    def test_cannot_reassign_own_patient_to_another_tenants_practitioner(self, client_a, patient_a, practitioner_b):
        res = client_a.patch(f"/api/accounts/patients/{patient_a.id}/", {
            "practitioner": practitioner_b.id,
        }, format="json")
        assert res.status_code == 400, res.data

        patient_a.refresh_from_db()
        assert patient_a.practitioner_id != practitioner_b.id


class TestAppointmentCrossTenantIsolation:
    def test_cannot_create_appointment_under_another_tenants_practitioner(self, client_a, practitioner_b, patient_a):
        res = client_a.post("/api/appointments/", {
            "practitioner": practitioner_b.id, "patient_id": patient_a.id,
            "start_time": (timezone.now() + timedelta(days=1)).isoformat(),
            "end_time": (timezone.now() + timedelta(days=1, hours=1)).isoformat(),
        }, format="json")
        assert res.status_code == 400, res.data

    def test_cannot_reassign_own_appointment_to_another_tenants_practitioner(
        self, client_a, practitioner_a, practitioner_b, patient_a
    ):
        from apps.appointments.models import Appointment
        appt = Appointment.objects.create(
            practitioner=practitioner_a, patient=patient_a,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
        )
        res = client_a.patch(f"/api/appointments/{appt.id}/", {
            "practitioner": practitioner_b.id,
        }, format="json")
        assert res.status_code == 400, res.data

        appt.refresh_from_db()
        assert appt.practitioner_id != practitioner_b.id


class TestAppointmentSeriesCrossTenantIsolation:
    def test_cannot_create_series_under_another_tenants_practitioner(self, client_a, practitioner_b, patient_a):
        res = client_a.post("/api/appointments/series/", {
            "practitioner": practitioner_b.id, "patient_id": patient_a.id,
            "frequency": "weekly", "first_start_time": (timezone.now() + timedelta(days=7)).isoformat(),
            "duration_minutes": 45, "occurrences_total": 3,
        }, format="json")
        assert res.status_code in (400, 403), res.data


class TestTimeSlotCrossTenantIsolation:
    def test_cannot_create_timeslot_under_another_tenants_practitioner(self, client_a, practitioner_b):
        start = timezone.now() + timedelta(days=1)
        res = client_a.post("/api/appointments/timeslots/", {
            "practitioner": practitioner_b.id,
            "start_time": start.isoformat(), "end_time": (start + timedelta(hours=1)).isoformat(),
        }, format="json")
        assert res.status_code == 400, res.data


class TestWaitlistEntryCrossTenantIsolation:
    def test_cannot_create_waitlist_entry_under_another_tenants_practitioner(
        self, client_a, practitioner_b, patient_a
    ):
        res = client_a.post("/api/appointments/waitlist/", {
            "practitioner": practitioner_b.id, "patient_id": patient_a.id,
        }, format="json")
        assert res.status_code == 400, res.data


class TestAvailabilityRuleCrossTenantIsolation:
    def test_cannot_create_rule_under_another_tenants_practitioner(self, client_a, practitioner_b):
        res = client_a.post("/api/appointments/availability-rules/", {
            "practitioner": practitioner_b.id, "weekday": 0,
            "start_time": "09:00:00", "end_time": "12:00:00", "slot_duration_minutes": 30,
        }, format="json")
        assert res.status_code == 400, res.data

    def test_cannot_reassign_own_rule_to_another_tenants_practitioner(self, client_a, practitioner_a, practitioner_b):
        from apps.appointments.models import AvailabilityRule
        rule = AvailabilityRule.objects.create(
            practitioner=practitioner_a, weekday=0,
            start_time="09:00:00", end_time="12:00:00", slot_duration_minutes=30,
        )
        res = client_a.patch(f"/api/appointments/availability-rules/{rule.id}/", {
            "practitioner": practitioner_b.id,
        }, format="json")
        assert res.status_code == 400, res.data

        rule.refresh_from_db()
        assert rule.practitioner_id != practitioner_b.id
