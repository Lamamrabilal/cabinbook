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

    logger.info("%d rappels programmés pour demain.", appointments.count())
