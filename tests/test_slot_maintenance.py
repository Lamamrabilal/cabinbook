"""
Maintenance des créneaux (TimeSlot) : génération optimisée (bulk_create au
lieu d'un get_or_create par créneau candidat) et purge des créneaux passés
pour empêcher la table de croître indéfiniment.
"""
import pytest
from datetime import timedelta, time
from django.utils import timezone


@pytest.fixture
def owner(db, django_user_model):
    return django_user_model.objects.create_user(
        username="slotmaint@example.com", email="slotmaint@example.com",
        password="testpass123", plan="pro", is_subscription_active=True,
    )


@pytest.fixture
def practitioner(db, owner):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=owner, first_name="Jean", last_name="Dupont", specialty="kine",
        booking_page_slug="jean-dupont-slotmaint-test",
    )


class TestGenerateSlotsQueryCount:
    def test_query_count_does_not_scale_with_number_of_candidate_slots(
        self, db, practitioner, django_assert_max_num_queries
    ):
        """Avant l'optimisation, un get_or_create par créneau candidat
        multipliait les requêtes par le nombre de créneaux générés. Ce test
        garantit que la génération reste à un nombre fixe de requêtes (une
        pour lire les créneaux existants, une pour le bulk_create) quel que
        soit l'horizon ou le nombre de créneaux dans la journée."""
        from apps.appointments.models import AvailabilityRule
        from apps.notifications.tasks import generate_slots_for_rule

        # Les règles ciblent des jours de la semaine décalés de plusieurs
        # jours dans le futur, pour que le premier créneau candidat soit
        # toujours dans le futur quelle que soit l'heure d'exécution du test.
        today = timezone.now()
        small_rule = AvailabilityRule.objects.create(
            practitioner=practitioner, weekday=(today.weekday() + 3) % 7,
            start_time=time(9, 0), end_time=time(10, 0), slot_duration_minutes=30,
        )
        with django_assert_max_num_queries(10) as small:
            generate_slots_for_rule(small_rule, horizon_days=8)

        big_rule = AvailabilityRule.objects.create(
            practitioner=practitioner, weekday=(today.weekday() + 4) % 7,
            start_time=time(0, 0), end_time=time(23, 45), slot_duration_minutes=15,
        )
        with django_assert_max_num_queries(len(small.captured_queries)):
            generate_slots_for_rule(big_rule, horizon_days=28)


class TestGenerateSlotsIdempotency:
    def test_calling_generate_twice_does_not_duplicate_slots(self, db, practitioner):
        from apps.appointments.models import AvailabilityRule, TimeSlot
        from apps.notifications.tasks import generate_slots_for_rule

        today = timezone.now()
        rule = AvailabilityRule.objects.create(
            practitioner=practitioner, weekday=today.weekday(),
            start_time=time(9, 0), end_time=time(12, 0), slot_duration_minutes=30,
        )

        first_created = generate_slots_for_rule(rule, horizon_days=14)
        assert first_created > 0

        second_created = generate_slots_for_rule(rule, horizon_days=14)
        assert second_created == 0
        assert TimeSlot.objects.filter(practitioner=practitioner).count() == first_created


class TestPurgeOldTimeslots:
    def test_purges_slots_older_than_one_day_keeps_recent_and_future(self, db, practitioner):
        from apps.appointments.models import TimeSlot
        from apps.notifications.tasks import purge_old_timeslots

        old = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() - timedelta(days=2),
            end_time=timezone.now() - timedelta(days=2) + timedelta(minutes=30),
        )
        recent_past = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() - timedelta(hours=2),
            end_time=timezone.now() - timedelta(hours=1, minutes=30),
        )
        future = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() + timedelta(days=1),
            end_time=timezone.now() + timedelta(days=1, minutes=30),
        )

        deleted = purge_old_timeslots()

        assert deleted == 1
        remaining_ids = set(TimeSlot.objects.values_list("id", flat=True))
        assert old.id not in remaining_ids
        assert recent_past.id in remaining_ids
        assert future.id in remaining_ids

    def test_purge_does_not_delete_the_linked_appointment_only_nulls_the_fk(self, db, practitioner):
        from apps.accounts.models import Patient
        from apps.appointments.models import TimeSlot, Appointment
        from apps.notifications.tasks import purge_old_timeslots

        patient = Patient.objects.create(
            practitioner=practitioner, first_name="Marie", last_name="Martin",
            email="marie.slotmaint@example.com",
        )
        old_slot = TimeSlot.objects.create(
            practitioner=practitioner,
            start_time=timezone.now() - timedelta(days=5),
            end_time=timezone.now() - timedelta(days=5) + timedelta(minutes=30),
        )
        appt = Appointment.objects.create(
            practitioner=practitioner, patient=patient, timeslot=old_slot,
            start_time=old_slot.start_time, end_time=old_slot.end_time,
            status=Appointment.STATUS_DONE,
        )

        purge_old_timeslots()

        appt.refresh_from_db()
        assert appt.timeslot_id is None
        assert Appointment.objects.filter(pk=appt.pk).exists()
