from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.appointments.models import Appointment


@receiver(post_save, sender=Appointment)
def sync_appointment_to_google_calendar(sender, instance, **kwargs):
    """
    Déclenche la synchro Google Calendar à chaque création/modification de
    RDV. C'est un signal (plutôt qu'un appel explicite à chaque point
    d'écriture) car les RDV sont créés/modifiés depuis de nombreux endroits
    (formulaire complet, réservation manuelle, réservation publique avec ou
    sans acompte, webhook Stripe, actions confirmer/annuler/terminer/absent,
    séries récurrentes) : un signal garantit qu'aucun de ces chemins n'est
    oublié, y compris ceux ajoutés plus tard.
    """
    from apps.accounts.models import GoogleCalendarConnection

    if not GoogleCalendarConnection.objects.filter(practitioner_id=instance.practitioner_id).exists():
        return
    from apps.notifications.tasks import sync_appointment_to_google
    sync_appointment_to_google.delay(instance.pk)
