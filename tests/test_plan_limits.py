"""
Couverture des différences de comportement entre les 3 offres (Starter, Pro,
Cabinet) : limites de ressources (praticiens, comptes secrétaire, salles),
fonctionnalités réservées (export iCal, séries récurrentes, statistiques
comparatives, SMS/WhatsApp), et les fuites de plafond via réactivation.
"""
import pytest
from unittest.mock import patch
from datetime import timedelta
from django.utils import timezone
from rest_framework.test import APIClient


def make_owner(django_user_model, plan, suffix):
    return django_user_model.objects.create_user(
        username=f"{suffix}@example.com", email=f"{suffix}@example.com",
        password="testpass123", plan=plan, is_subscription_active=True,
    )


def make_client(owner):
    c = APIClient()
    c.force_authenticate(user=owner)
    return c


def make_practitioner(owner, suffix):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="P", last_name=suffix, specialty="kine",
        booking_page_slug=f"p-{suffix}-plan-test",
    )


def make_patient(practitioner, suffix):
    from apps.accounts.models import Patient
    return Patient.objects.create(
        practitioner=practitioner, first_name="Pat", last_name=suffix,
        email=f"pat-{suffix}@example.com",
    )


@pytest.fixture(params=["starter", "pro", "cabinet"])
def plan(request):
    return request.param


@pytest.fixture
def owner(db, django_user_model, plan):
    return make_owner(django_user_model, plan, f"owner-{plan}")


@pytest.fixture
def client(owner):
    return make_client(owner)


class TestMaxPractitioners:
    LIMITS = {"starter": 1, "pro": 1, "cabinet": 5}

    def test_can_create_up_to_the_limit_but_not_beyond(self, client, owner, plan):
        limit = self.LIMITS[plan]
        for i in range(limit):
            res = client.post("/api/accounts/practitioners/", {
                "first_name": "P", "last_name": str(i), "specialty": "kine",
                "booking_page_slug": f"limit-{plan}-{i}",
            })
            assert res.status_code == 201, res.data

        res = client.post("/api/accounts/practitioners/", {
            "first_name": "P", "last_name": "over", "specialty": "kine",
            "booking_page_slug": f"limit-{plan}-over",
        })
        assert res.status_code == 400, res.data

    def test_reactivating_a_practitioner_cannot_bypass_the_limit(self, db, django_user_model):
        """Régression : désactiver un praticien au plafond, en créer un nouveau,
        puis réactiver l'ancien ne doit jamais dépasser la limite du plan."""
        owner = make_owner(django_user_model, "pro", "reactivate-practitioner")
        client = make_client(owner)
        p1 = make_practitioner(owner, "one")

        deactivate_res = client.post(f"/api/accounts/practitioners/{p1.id}/deactivate/")
        assert deactivate_res.status_code == 200

        create_res = client.post("/api/accounts/practitioners/", {
            "first_name": "P", "last_name": "two", "specialty": "kine",
            "booking_page_slug": "reactivate-practitioner-two",
        })
        assert create_res.status_code == 201, create_res.data

        reactivate_res = client.patch(f"/api/accounts/practitioners/{p1.id}/", {"is_active": True}, format="json")
        assert reactivate_res.status_code == 400, reactivate_res.data

        from apps.accounts.models import Practitioner
        assert Practitioner.objects.filter(owner=owner, is_active=True).count() == 1

    def test_editing_an_already_active_practitioner_is_not_blocked(self, db, django_user_model):
        """Le correctif ne doit pas bloquer une simple modification (téléphone,
        etc.) d'un praticien déjà actif qui reste actif."""
        owner = make_owner(django_user_model, "starter", "edit-active-practitioner")
        client = make_client(owner)
        p1 = make_practitioner(owner, "one")

        res = client.patch(f"/api/accounts/practitioners/{p1.id}/", {"phone": "0600000000"}, format="json")
        assert res.status_code == 200, res.data


class TestMaxStaffAccounts:
    LIMITS = {"starter": 0, "pro": 1, "cabinet": 3}

    def test_can_create_up_to_the_limit_but_not_beyond(self, client, owner, plan):
        limit = self.LIMITS[plan]
        for i in range(limit):
            res = client.post("/api/accounts/staff/", {
                "email": f"staff-{plan}-{i}@example.com", "first_name": "S", "last_name": str(i),
            })
            assert res.status_code == 201, res.data

        res = client.post("/api/accounts/staff/", {
            "email": f"staff-{plan}-over@example.com", "first_name": "S", "last_name": "over",
        })
        assert res.status_code == 403, res.data

    def test_reactivating_a_staff_account_after_downgrade_cannot_bypass_the_limit(self, db, django_user_model):
        """Régression : un titulaire qui redescend de Cabinet à Pro garde ses
        comptes secrétaire existants (grandfathering), mais ne doit pas pouvoir
        réactiver un compte désactivé au-delà du plafond de son nouveau plan."""
        owner = make_owner(django_user_model, "cabinet", "downgrade-staff")
        client = make_client(owner)

        res_a = client.post("/api/accounts/staff/", {"email": "sa@example.com", "first_name": "A", "last_name": "A"})
        res_b = client.post("/api/accounts/staff/", {"email": "sb@example.com", "first_name": "B", "last_name": "B"})
        assert res_a.status_code == 201 and res_b.status_code == 201
        staff_a_id = res_a.data["id"]
        staff_b_id = res_b.data["id"]

        owner.plan = "pro"  # max_staff passe de 3 à 1
        owner.save(update_fields=["plan"])

        deactivate_res = client.post(f"/api/accounts/staff/{staff_b_id}/deactivate/")
        assert deactivate_res.status_code == 200

        reactivate_res = client.patch(f"/api/accounts/staff/{staff_b_id}/", {"is_active": True}, format="json")
        assert reactivate_res.status_code == 403, reactivate_res.data

        from apps.accounts.models import User
        assert User.objects.filter(owner_account=owner, is_active=True).count() == 1


class TestRoomManagementByPlan:
    def test_only_cabinet_plan_can_create_rooms(self, client, owner, plan):
        res = client.post("/api/accounts/rooms/", {"name": "Salle 1"})
        if plan == "cabinet":
            assert res.status_code == 201, res.data
        else:
            assert res.status_code == 403, res.data

    def test_reactivating_a_room_after_downgrade_cannot_bypass_the_limit(self, db, django_user_model):
        owner = make_owner(django_user_model, "cabinet", "downgrade-room")
        client = make_client(owner)

        res = client.post("/api/accounts/rooms/", {"name": "Salle X"})
        assert res.status_code == 201, res.data
        room_id = res.data["id"]

        owner.plan = "starter"  # plus aucune salle autorisée
        owner.save(update_fields=["plan"])

        # Un titulaire Starter garde sa salle existante (grandfathering)...
        assert client.get("/api/accounts/rooms/").data[0]["is_active"] is True

        patch_deactivate = client.patch(f"/api/accounts/rooms/{room_id}/", {"is_active": False}, format="json")
        assert patch_deactivate.status_code == 200

        # ...mais ne doit pas pouvoir la réactiver une fois désactivée.
        patch_reactivate = client.patch(f"/api/accounts/rooms/{room_id}/", {"is_active": True}, format="json")
        assert patch_reactivate.status_code == 403, patch_reactivate.data


class TestStatsByPractitionerReservedToCabinet:
    def test_access_by_plan(self, client, plan):
        res = client.get("/api/appointments/stats_by_practitioner/")
        if plan == "cabinet":
            assert res.status_code == 200
        else:
            assert res.status_code == 403


class TestExportIcalReservedToProAndCabinet:
    def test_access_by_plan(self, client, plan):
        res = client.get("/api/appointments/export_ical/")
        if plan == "starter":
            assert res.status_code == 403
        else:
            assert res.status_code == 200


class TestRecurringSeriesReservedToProAndCabinet:
    def test_access_by_plan(self, client, owner, plan):
        practitioner = make_practitioner(owner, "series")
        patient = make_patient(practitioner, "series")
        payload = {
            "practitioner": practitioner.id, "patient_id": patient.id,
            "frequency": "weekly", "first_start_time": (timezone.now() + timedelta(days=7)).isoformat(),
            "duration_minutes": 45, "occurrences_total": 3,
        }
        res = client.post("/api/appointments/series/", payload, format="json")
        if plan == "starter":
            assert res.status_code == 403, res.data
        else:
            assert res.status_code in (200, 201), res.data


class TestReminderChannelsByPlan:
    def test_sms_reminder_skipped_on_starter_sent_on_pro_and_cabinet(self, db, owner, plan):
        from apps.appointments.models import Appointment
        from apps.notifications.tasks import send_appointment_reminder_sms

        practitioner = make_practitioner(owner, "sms")
        patient = make_patient(practitioner, "sms")
        patient.phone = "+33600000000"
        patient.save(update_fields=["phone"])
        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, hours=1),
            status=Appointment.STATUS_CONFIRMED,
        )
        with patch("apps.notifications.services.SmsService.send_reminder") as mock_sms:
            send_appointment_reminder_sms(appt.pk)

        if plan == "starter":
            mock_sms.assert_not_called()
        else:
            mock_sms.assert_called_once()


class TestInvalidPlanOnCheckout:
    def test_invalid_plan_returns_400(self, db, django_user_model):
        owner = make_owner(django_user_model, "starter", "checkout-invalid")
        client = make_client(owner)
        res = client.post("/api/billing/checkout/", {"plan": "not-a-real-plan"}, format="json")
        assert res.status_code == 400
