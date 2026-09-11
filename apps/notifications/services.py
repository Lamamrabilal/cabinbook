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

        video_html = ""
        if appointment.video_room_url:
            video_html = f"""
            <p>
              📹 Ce rendez-vous peut se faire en visioconférence :
              <a href="{appointment.video_room_url}">rejoindre la salle de téléconsultation</a>
            </p>
            """

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=patient.email,
            subject=f"Confirmation RDV — {start}",
            html_content=f"""
            <p>Bonjour {patient.first_name},</p>
            <p>Votre rendez-vous est confirmé : <strong>{start}</strong>
               avec <strong>{practitioner}</strong>.</p>
            {video_html}
            <p>
              <a href="{settings.FRONTEND_URL}/cancel/{appointment.cancellation_token}">
                Annuler ce rendez-vous
              </a>
            </p>
            """,
        )

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)


    @staticmethod
    def send_review_request(appointment):
        """Invite le patient à laisser un avis après une séance terminée."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        patient = appointment.patient
        practitioner = appointment.practitioner
        review_url = f"{settings.SITE_URL}/avis/{appointment.confirmation_token}/"

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=patient.email,
            subject=f"Votre avis sur votre séance avec {practitioner}",
            html_content=f"""
            <p>Bonjour {patient.first_name},</p>
            <p>Votre séance avec <strong>{practitioner}</strong> est terminée.
               Votre avis aide les futurs patients et le praticien à s'améliorer.</p>
            <p>
              <a href="{review_url}">
                Laisser un avis
              </a>
            </p>
            <p>À bientôt,<br>CabinBook</p>
            """,
        )

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)

    @staticmethod
    def send_password_reset(user, reset_url):
        """Email de reinitialisation de mot de passe."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=user.email,
            subject="Reinitialisation de votre mot de passe CabinBook",
            html_content=f"""
            <p>Bonjour {user.first_name or ""},</p>
            <p>Vous avez demande la reinitialisation de votre mot de passe CabinBook.</p>
            <p>
              <a href="{reset_url}">
                Choisir un nouveau mot de passe
              </a>
            </p>
            <p>Si vous n'etes pas a l'origine de cette demande, ignorez simplement cet email.</p>
            <p>Ce lien expire apres un usage unique ou apres un delai de securite.</p>
            <p>A bientot,<br>CabinBook</p>
            """,
        )
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)

    @staticmethod
    def send_staff_account_created(staff_user, owner, temp_password):
        """Email envoye a un compte secretaire nouvellement cree, avec son mot de passe temporaire."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=staff_user.email,
            subject="Votre acces CabinBook",
            html_content=f"""
            <p>Bonjour {staff_user.first_name or ""},</p>
            <p>{owner.get_full_name() or owner.email} vous a cree un acces secretaire sur CabinBook.</p>
            <p>
              Email de connexion : <strong>{staff_user.email}</strong><br>
              Mot de passe temporaire : <strong>{temp_password}</strong>
            </p>
            <p>
              <a href="{settings.FRONTEND_URL}">Se connecter</a>
            </p>
            <p>Nous vous recommandons de changer ce mot de passe apres votre premiere connexion
               (rubrique "Mot de passe oublie" sur la page de connexion).</p>
            <p>A bientot,<br>CabinBook</p>
            """,
        )
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)

    @staticmethod
    def send_subscription_confirmation(user, plan):
        """Email de confirmation d'activation d'abonnement."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        plan_labels = {
            "starter": "Starter (29€/mois)",
            "pro": "Pro (49€/mois)",
            "cabinet": "Cabinet (99€/mois)",
        }
        plan_label = plan_labels.get(plan, plan)

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=user.email,
            subject="Votre abonnement CabinBook est actif",
            html_content=f"""
            <p>Bonjour {user.first_name or ""},</p>
            <p>Votre abonnement <strong>{plan_label}</strong> est maintenant actif.</p>
            <p>Vous pouvez des a present configurer vos disponibilites et partager votre lien de reservation a vos patients.</p>
            <p>
              <a href="{settings.FRONTEND_URL}">
                Acceder a mon tableau de bord
              </a>
            </p>
            <p>Merci de votre confiance,<br>CabinBook</p>
            """,
        )
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)


    @staticmethod
    def send_waitlist_notification(entry):
        """Prévient un patient en liste d'attente qu'un créneau vient de se libérer."""
        import sendgrid
        from sendgrid.helpers.mail import Mail

        patient = entry.patient
        practitioner = entry.practitioner
        booking_url = f"{settings.SITE_URL}/book/{practitioner.booking_page_slug}/"

        message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=patient.email,
            subject=f"Un créneau vient de se libérer chez {practitioner}",
            html_content=f"""
            <p>Bonjour {patient.first_name},</p>
            <p>Un créneau vient de se libérer chez <strong>{practitioner}</strong>.
               Vous êtes sur liste d'attente : réservez-le avant qu'il ne soit repris.</p>
            <p>
              <a href="{booking_url}">
                Réserver un créneau
              </a>
            </p>
            <p>À bientôt,<br>CabinBook</p>
            """,
        )

        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(message)

    @staticmethod
    def send_contact_message(name, email, message):
        """Transmet un message du formulaire de contact vers l'adresse de support."""
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email

        contact_message = Mail(
            from_email=settings.DEFAULT_FROM_EMAIL,
            to_emails=settings.DEFAULT_FROM_EMAIL,
            subject=f"Nouveau message de contact CabinBook — {name}",
            html_content=f"""
            <p><strong>De :</strong> {name} ({email})</p>
            <p><strong>Message :</strong></p>
            <p>{message}</p>
            """,
        )
        contact_message.reply_to = Email(email)
        sg = sendgrid.SendGridAPIClient(api_key=settings.SENDGRID_API_KEY)
        sg.send(contact_message)


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


class WhatsAppService:
    @staticmethod
    def send_reminder(appointment):
        """
        Rappel WhatsApp via Twilio (canal additionnel à l'email/SMS).
        Nécessite un numéro WhatsApp Business validé sur le compte Twilio
        (settings.TWILIO_WHATSAPP_FROM_NUMBER) — sinon cette méthode ne doit
        pas être appelée (voir tasks.send_appointment_reminder_whatsapp).
        """
        from twilio.rest import Client

        patient = appointment.patient
        practitioner = appointment.practitioner
        start = appointment.start_time.strftime("%d/%m à %H:%M")

        body = (
            f"Rappel CabinBook : RDV demain {start} avec {practitioner.last_name}. "
            f"Annuler : {settings.SITE_URL}/api/public/book/cancel/{appointment.cancellation_token}/"
        )

        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message = client.messages.create(
            body=body,
            from_=f"whatsapp:{settings.TWILIO_WHATSAPP_FROM_NUMBER}",
            to=f"whatsapp:{patient.phone}",
        )
        logger.info("WhatsApp envoyé à %s (SID: %s)", patient.phone, message.sid)
