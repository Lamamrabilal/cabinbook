import pytest
from unittest.mock import patch
from rest_framework.test import APIClient


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="titulaire@example.com",
        email="titulaire@example.com",
        password="testpass123",
        is_subscription_active=True,
        plan="cabinet",
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner,
        first_name="Jean",
        last_name="Dupont",
        specialty="kine",
        booking_page_slug="jean-dupont-staff-test",
    )


@pytest.fixture
def secretary(db, owner):
    from apps.accounts.models import User
    return User.objects.create_user(
        username="secretaire@example.com",
        email="secretaire@example.com",
        password="testpass123",
        role=User.ROLE_SECRETARY,
        owner_account=owner,
    )


@pytest.fixture
def owner_client(owner):
    client = APIClient()
    client.force_authenticate(user=owner)
    return client


@pytest.fixture
def secretary_client(secretary):
    client = APIClient()
    client.force_authenticate(user=secretary)
    return client


class TestEffectiveOwner:
    def test_owner_is_its_own_effective_owner(self, owner):
        assert owner.effective_owner == owner

    def test_secretary_effective_owner_is_the_owner(self, owner, secretary):
        assert secretary.effective_owner == owner

    def test_secretary_inherits_owner_plan_via_serializer(self, secretary_client, owner):
        res = secretary_client.get("/api/accounts/me/")
        assert res.status_code == 200
        assert res.data["plan"] == owner.plan  # "cabinet", pas le plan (vide) du secretaire
        assert res.data["role"] == "secretary"
        assert res.data["owner_name"]


class TestStaffAccountViewSet:
    @patch("apps.notifications.services.EmailService.send_staff_account_created")
    def test_owner_can_create_secretary(self, mock_email, owner_client, owner):
        res = owner_client.post("/api/accounts/staff/", {
            "email": "nouvelle.secretaire@example.com",
            "first_name": "Alice",
            "last_name": "Martin",
        })
        assert res.status_code == 201, res.data
        mock_email.assert_called_once()

        from apps.accounts.models import User
        created = User.objects.get(email="nouvelle.secretaire@example.com")
        assert created.role == User.ROLE_SECRETARY
        assert created.owner_account == owner
        assert created.has_usable_password()

    def test_owner_cannot_exceed_max_staff(self, owner_client, owner, secretary):
        # plan cabinet => max_staff = 3 ; on cree 2 de plus (total 3 avec `secretary`), la 4e doit echouer
        for i in range(2):
            res = owner_client.post("/api/accounts/staff/", {
                "email": f"secretaire{i}@example.com", "first_name": "S", "last_name": str(i),
            })
            assert res.status_code == 201, res.data

        res = owner_client.post("/api/accounts/staff/", {
            "email": "secretaire.trop@example.com", "first_name": "S", "last_name": "Trop",
        })
        assert res.status_code == 403

    def test_secretary_cannot_list_or_create_staff(self, secretary_client):
        res = secretary_client.get("/api/accounts/staff/")
        assert res.status_code == 403

        res = secretary_client.post("/api/accounts/staff/", {
            "email": "autre@example.com", "first_name": "A", "last_name": "B",
        })
        assert res.status_code == 403

    def test_secretary_not_visible_to_other_owners(self, db, django_user_model, secretary):
        other_owner = django_user_model.objects.create_user(
            username="autretitulaire@example.com", email="autretitulaire@example.com",
            password="testpass123", plan="cabinet",
        )
        client = APIClient()
        client.force_authenticate(user=other_owner)
        res = client.get("/api/accounts/staff/")
        assert res.status_code == 200
        assert len(res.data) == 0


class TestSecretaryScopedAccess:
    def test_secretary_sees_owner_practitioners(self, secretary_client, practitioner):
        res = secretary_client.get("/api/accounts/practitioners/")
        assert res.status_code == 200
        assert len(res.data) == 1
        assert res.data[0]["id"] == practitioner.id

    def test_secretary_can_create_patient_for_owner_practitioner(self, secretary_client, practitioner):
        res = secretary_client.post("/api/accounts/patients/", {
            "practitioner": practitioner.id,
            "first_name": "Marie",
            "last_name": "Martin",
            "email": "marie.patient@example.com",
        })
        assert res.status_code == 201, res.data

    def test_secretary_can_see_appointments(self, secretary_client, practitioner, owner):
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import Patient
        from apps.appointments.models import Appointment

        patient = Patient.objects.create(
            practitioner=practitioner, first_name="Marie", last_name="Martin",
            email="marie2@example.com",
        )
        Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CONFIRMED,
        )
        res = secretary_client.get("/api/appointments/")
        assert res.status_code == 200
        assert res.data["count"] == 1 if isinstance(res.data, dict) else len(res.data) == 1


class TestSecretaryRestrictions:
    def test_secretary_cannot_access_billing_checkout(self, secretary_client):
        res = secretary_client.post("/api/billing/checkout/", {"plan": "pro"})
        assert res.status_code == 403

    def test_secretary_cannot_cancel_subscription(self, secretary_client):
        res = secretary_client.post("/api/billing/cancel/")
        assert res.status_code == 403

    def test_secretary_cannot_access_session_note(self, secretary_client, practitioner, owner):
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import Patient
        from apps.appointments.models import Appointment

        patient = Patient.objects.create(
            practitioner=practitioner, first_name="Marie", last_name="Martin",
            email="marie3@example.com",
        )
        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CONFIRMED,
        )
        res = secretary_client.get(f"/api/appointments/{appt.id}/note/")
        assert res.status_code == 403

    def test_owner_can_access_session_note(self, owner_client, practitioner, owner):
        from django.utils import timezone
        from datetime import timedelta
        from apps.accounts.models import Patient
        from apps.appointments.models import Appointment

        patient = Patient.objects.create(
            practitioner=practitioner, first_name="Marie", last_name="Martin",
            email="marie4@example.com",
        )
        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CONFIRMED,
        )
        res = owner_client.get(f"/api/appointments/{appt.id}/note/")
        assert res.status_code == 200
