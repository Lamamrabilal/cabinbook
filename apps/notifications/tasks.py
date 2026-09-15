import logging
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def send_appointment_reminder_email(self, appointment_id: int):
    """Envoie un rappel email J-1 avant le RDV."""
    from apps.appointments.models import Appointment
    from apps.notifications.services import EmailService

    try:
        appt = Appointment.objects.select_related("patient", "practitioner").get(pk=appointment_id)
        if appt.status != Appointment.STATUS_CONFIRMED:
            logger.info("RDV %s non confirmé, rappel email annulé.", appointment_id)
            return

        EmailService.send_reminder(appt)
        appt.reminder_email_sent = True
        appt.save(update_fields=["reminder_email_sent"])
        logger.info("Rappel email envoyé pour RDV %s", appointment_id)

    except Appointment.DoesNotExist:
        logger.error("Appointment %s introuvable", appointment_id)
    except Exception as exc:
        logger.error("Erreur rappel email RDV %s : %s", appointment_id, exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_appointment_reminder_sms(self, appointment_id: int):
    """Envoie un rappel SMS J-1 avant le RDV (plan Pro/Cabinet)."""
    from apps.appointments.models import Appointment
    from apps.notifications.services import SmsService

    try:
        appt = Appointment.objects.select_related("patient", "practitioner__owner").get(pk=appointment_id)

        if appt.practitioner.owner.plan == "starter":
            logger.info("Plan Starter — SMS non inclus pour RDV %s", appointment_id)
            return

        if appt.status != Appointment.STATUS_CONFIRMED or not appt.patient.phone:
            return

        SmsService.send_reminder(appt)
        appt.reminder_sms_sent = True
        appt.save(update_fields=["reminder_sms_sent"])
        logger.info("Rappel SMS envoyé pour RDV %s", appointment_id)

    except Exception as exc:
        logger.error("Erreur rappel SMS RDV %s : %s", appointment_id, exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task(bind=True, max_retries=3)
def send_appointment_reminder_whatsapp(self, appointment_id: int):
    """Envoie un rappel WhatsApp J-1 avant le RDV (plan Pro/Cabinet, en plus de l'email/SMS)."""
    from django.conf import settings
    from apps.appointments.models import Appointment
    from apps.notifications.services import WhatsAppService

    if not settings.TWILIO_WHATSAPP_FROM_NUMBER:
        return  # Sender WhatsApp Business non configuré côté Twilio — canal inactif.

    try:
        appt = Appointment.objects.select_related("patient", "practitioner__owner").get(pk=appointment_id)

        if appt.practitioner.owner.plan == "starter":
            return

        if appt.status != Appointment.STATUS_CONFIRMED or not appt.patient.phone:
            return

        WhatsAppService.send_reminder(appt)
        appt.reminder_whatsapp_sent = True
        appt.save(update_fields=["reminder_whatsapp_sent"])
        logger.info("Rappel WhatsApp envoyé pour RDV %s", appointment_id)

    except Exception as exc:
        logger.error("Erreur rappel WhatsApp RDV %s : %s", appointment_id, exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task
def schedule_reminders_for_tomorrow():
    """
    Tâche Celery Beat — lancée chaque jour à 10h.
    Programme les rappels pour tous les RDV du lendemain.
    """
    from apps.appointments.models import Appointment

    tomorrow_start = timezone.now().replace(hour=0, minute=0, second=0) + timedelta(days=1)
    tomorrow_end = tomorrow_start + timedelta(days=1)

    appointments = Appointment.objects.filter(
        start_time__range=(tomorrow_start, tomorrow_end),
        status=Appointment.STATUS_CONFIRMED,
        reminder_email_sent=False,
    ).select_related("patient", "practitioner__owner")

    for appt in appointments:
        send_appointment_reminder_email.delay(appt.pk)
        send_appointment_reminder_sms.delay(appt.pk)
        send_appointment_reminder_whatsapp.delay(appt.pk)

    logger.info("%d rappels programmés pour demain.", appointments.count())

def generate_slots_for_rule(rule, horizon_days=14):
    """
    Génère les créneaux (TimeSlot) d'une règle de disponibilité récurrente
    pour les `horizon_days` prochains jours. Idempotent (ne recrée pas les
    créneaux déjà existants) et ignore les créneaux déjà passés (pertinent
    pour le jour même : une règle activée à 15h ne doit pas créer de
    créneau à 9h). Utilisée à la fois par la tâche Celery quotidienne et
    immédiatement à la création/activation d'une règle, pour que les
    créneaux du jour et du lendemain soient réservables sans attendre le
    prochain passage de la tâche planifiée.

    Calcule d'abord tous les créneaux candidats en mémoire, puis ne fait que
    deux requêtes SQL au total (un SELECT pour connaître les créneaux déjà
    existants, un bulk_create pour les manquants) au lieu d'un get_or_create
    par créneau — déterminant pour une règle couvrant une longue plage
    horaire ou un horizon de plusieurs semaines.
    """
    from datetime import timedelta, datetime
    from apps.appointments.models import TimeSlot

    today = timezone.now().date()
    now = timezone.now()
    duration = timedelta(minutes=rule.slot_duration_minutes)
    candidates = []

    for offset in range(horizon_days):
        day = today + timedelta(days=offset)
        if day.weekday() != rule.weekday:
            continue

        current_dt = timezone.make_aware(datetime.combine(day, rule.start_time))
        end_dt = timezone.make_aware(datetime.combine(day, rule.end_time))

        while current_dt + duration <= end_dt:
            slot_end = current_dt + duration
            if current_dt >= now:
                candidates.append((current_dt, slot_end))
            current_dt = slot_end

    if not candidates:
        return 0

    existing_starts = set(
        TimeSlot.objects.filter(
            practitioner=rule.practitioner,
            start_time__in=[start for start, _ in candidates],
        ).values_list("start_time", flat=True)
    )

    new_slots = [
        TimeSlot(practitioner=rule.practitioner, start_time=start, end_time=end, is_available=True)
        for start, end in candidates
        if start not in existing_starts
    ]
    TimeSlot.objects.bulk_create(new_slots)

    return len(new_slots)


@shared_task
def generate_slots_from_availability():
    """
    Tâche Celery Beat — génère les créneaux (TimeSlot) des 14 prochains jours
    à partir des règles de disponibilité récurrentes (AvailabilityRule) de
    chaque praticien. Idempotent : ne recrée pas les créneaux déjà existants.
    """
    from apps.appointments.models import AvailabilityRule

    created_count = 0
    rules = AvailabilityRule.objects.filter(is_active=True).select_related("practitioner")
    for rule in rules:
        created_count += generate_slots_for_rule(rule)

    logger.info("%d nouveaux creneaux generes depuis les regles de disponibilite.", created_count)
    return created_count


@shared_task
def purge_old_timeslots():
    """
    Tâche Celery Beat — supprime les créneaux (TimeSlot) dont l'horaire de
    début remonte à plus d'un jour, pour empêcher la table de croître
    indéfiniment (elle est régénérée quotidiennement par
    generate_slots_from_availability, donc les vieux créneaux passés
    n'ont plus aucune utilité). Sans danger pour l'historique des RDV :
    Appointment.timeslot est en SET_NULL et chaque RDV conserve son propre
    start_time/end_time indépendamment du TimeSlot d'origine.
    """
    from apps.appointments.models import TimeSlot

    cutoff = timezone.now() - timedelta(days=1)
    deleted_count, _ = TimeSlot.objects.filter(start_time__lt=cutoff).delete()

    logger.info("%d anciens creneaux purges (anterieurs a %s).", deleted_count, cutoff)
    return deleted_count


@shared_task(bind=True, max_retries=3)
def sync_appointment_to_google(self, appointment_id):
    """
    Pousse l'état d'un RDV vers le Google Calendar connecté de son praticien
    (créé/mis à jour s'il est confirmé, supprimé s'il est annulé). Ne fait
    rien si le praticien n'a pas connecté de calendrier. Déclenché par le
    signal post_save sur Appointment (apps/appointments/signals.py).
    """
    from apps.appointments.models import Appointment
    from apps.accounts.models import GoogleCalendarConnection
    from apps.accounts import google_calendar

    try:
        appt = Appointment.objects.select_related("practitioner", "patient").get(pk=appointment_id)
    except Appointment.DoesNotExist:
        return

    try:
        connection = GoogleCalendarConnection.objects.get(practitioner_id=appt.practitioner_id)
    except GoogleCalendarConnection.DoesNotExist:
        return

    try:
        if appt.status == Appointment.STATUS_CANCELLED:
            google_calendar.delete_event(connection, appt)
            Appointment.objects.filter(pk=appt.pk).update(google_event_id="")
        elif appt.status == Appointment.STATUS_CONFIRMED:
            event_id = google_calendar.upsert_event(connection, appt)
            Appointment.objects.filter(pk=appt.pk).update(google_event_id=event_id)
        # PENDING / DONE / NO_SHOW : pas de synchro (DONE/NO_SHOW gardent
        # l'événement existant tel quel comme trace historique).
    except google_calendar.GoogleCalendarError as exc:
        logger.warning("Echec synchro Google Calendar pour RDV %s : %s", appointment_id, exc)
        raise self.retry(exc=exc, countdown=300)


@shared_task
def sync_busy_periods_from_google():
    """
    Tâche Celery Beat — pour chaque praticien connecté à Google Calendar,
    bloque les créneaux CabinBook disponibles qui chevauchent un événement
    de son agenda perso (anti double-booking), et libère ceux précédemment
    bloqués dont l'événement externe a disparu. Ne touche jamais un créneau
    déjà occupé par un vrai RDV CabinBook.
    """
    from datetime import datetime
    from apps.accounts.models import GoogleCalendarConnection
    from apps.appointments.models import TimeSlot
    from apps.accounts import google_calendar

    now = timezone.now()
    horizon = now + timedelta(days=14)
    connections = GoogleCalendarConnection.objects.filter(
        sync_busy_from_google=True
    ).select_related("practitioner")

    for connection in connections:
        try:
            busy_periods = google_calendar.get_busy_periods(connection, now, horizon)
        except google_calendar.GoogleCalendarError as exc:
            logger.warning(
                "Echec recuperation freebusy Google Calendar pour praticien %s : %s",
                connection.practitioner_id, exc,
            )
            continue

        busy_ranges = [
            (datetime.fromisoformat(period["start"]), datetime.fromisoformat(period["end"]))
            for period in busy_periods
        ]

        slots = TimeSlot.objects.filter(
            practitioner=connection.practitioner,
            start_time__gte=now, start_time__lte=horizon,
        )
        for slot in slots:
            is_busy = any(
                b_start < slot.end_time and b_end > slot.start_time for b_start, b_end in busy_ranges
            )
            if is_busy and slot.is_available:
                slot.is_available = False
                slot.blocked_by_external_calendar = True
                slot.save(update_fields=["is_available", "blocked_by_external_calendar"])
            elif not is_busy and slot.blocked_by_external_calendar:
                slot.is_available = True
                slot.blocked_by_external_calendar = False
                slot.save(update_fields=["is_available", "blocked_by_external_calendar"])
