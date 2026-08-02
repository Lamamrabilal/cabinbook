import logging
from django.conf import settings

logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    def send_reminder(appointment):
        """Rappel email J-1 via SendGrid."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        patient = appointment.patient
        practitioner = appointment.practitioner
        start = appointment.start_time.strftime("%d/%m/%Y à %H:%M")

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=patient.email,
            subject=f"Rappel RDV — {start} avec {practitioner}",
            html_content=f"""
            <p>Bonjour {patient.first_name},</p>
            <p>Rappel de votre rendez-vous <strong>demain {start}</strong>
               avec <strong>{practitioner}</strong>.</p>
            <p>
              <a href="{settings.FRONTEND_URL}/confirm/{appointment.confirmation_token}">
                ✅ Confirmer ma présence
              </a>
              &nbsp;|&nbsp;
              <a href="{settings.FRONTEND_URL}/cancel/{appointment.cancellation_token}">
                ❌ Annuler
              </a>
            </p>
            <p>À bientôt,<br>CabinBook</p>
            """,
        )

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        response = sg.send(message)
        logger.info("Email rappel envoyé à %s (status %s)", patient.email, response.status_code)

    @staticmethod
    def send_confirmation(appointment):
        """Email de confirmation immédiate à la prise de RDV."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        patient = appointment.patient
        practitioner = appointment.practitioner
        start = appointment.start_time.strftime("%d/%m/%Y à %H:%M")

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=patient.email,
            subject=f"Confirmation RDV — {start}",
            html_content=f"""
            <p>Bonjour {patient.first_name},</p>
            <p>Votre rendez-vous est confirmé : <strong>{start}</strong>
               avec <strong>{practitioner}</strong>.</p>
            <p>
              <a href="{settings.FRONTEND_URL}/cancel/{appointment.cancellation_token}">
                Annuler ce rendez-vous
              </a>
            </p>
            """,
        )

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)


class SmsService:
    @staticmethod
    def send_reminder(appointment):
        """Rappel SMS via Twilio."""
        from twilio.rest import Client

        patient = appointment.patient
        practitioner = appointment.practitioner
        start = appointment.start_time.strftime("%d/%m à %H:%M")

        body = (
            f"Rappel CabinBook : RDV demain {start} "
            f"avec {practitioner.last_name}. "
            f"Annuler : {settings.FRONTEND_URL}/cancel/{appointment.cancellation_token}"
        )

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=settings.TWILIO_FROM_NUMBER,
            to=patient.phone,
        )
        logger.info("SMS envoyé à %s (SID: %s)", patient.phone, message.sid)
