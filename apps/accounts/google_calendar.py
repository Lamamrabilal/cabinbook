"""
Intégration Google Calendar : OAuth2 (connexion du praticien) et appels à
l'API Calendar v3 pour pousser les RDV confirmés et lire les périodes
occupées de son agenda personnel. Implémenté en appels HTTP directs
(requests) plutôt qu'avec le SDK google-api-python-client, pour rester léger.
"""
import requests
from datetime import timedelta
from urllib.parse import urlencode
from django.conf import settings
from django.core import signing
from django.utils import timezone

AUTH_BASE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"
CALENDAR_API_BASE = "https://www.googleapis.com/calendar/v3"
SCOPE = "https://www.googleapis.com/auth/calendar.events https://www.googleapis.com/auth/userinfo.email"
STATE_SALT = "google-calendar-oauth"


class GoogleCalendarError(Exception):
    """Erreur lors d'un appel à l'API OAuth ou Calendar de Google."""


def build_authorization_url(practitioner):
    """URL vers laquelle rediriger le navigateur pour démarrer la connexion OAuth."""
    state = signing.dumps({"practitioner_id": practitioner.id}, salt=STATE_SALT)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_BASE_URL}?{urlencode(params)}"


def parse_state(state):
    """Décode le practitioner_id encodé dans le paramètre state, ou None si invalide/expiré (>10 min)."""
    try:
        data = signing.loads(state, salt=STATE_SALT, max_age=600)
    except signing.BadSignature:
        return None
    return data.get("practitioner_id")


def exchange_code_for_tokens(code):
    """Échange le code d'autorisation contre un access_token + refresh_token."""
    resp = requests.post(TOKEN_URL, data={
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
        "code": code,
    }, timeout=10)
    if not resp.ok:
        raise GoogleCalendarError(f"Échange de code échoué : {resp.text}")
    return resp.json()


def fetch_google_email(access_token):
    resp = requests.get(USERINFO_URL, headers={"Authorization": f"Bearer {access_token}"}, timeout=10)
    if resp.ok:
        return resp.json().get("email", "")
    return ""


def _refresh_access_token(connection):
    resp = requests.post(TOKEN_URL, data={
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": connection.refresh_token,
    }, timeout=10)
    if not resp.ok:
        raise GoogleCalendarError(f"Rafraîchissement du token échoué : {resp.text}")
    data = resp.json()
    connection.access_token = data["access_token"]
    connection.token_expiry = timezone.now() + timedelta(seconds=data.get("expires_in", 3600))
    connection.save(update_fields=["access_token", "token_expiry"])
    return connection.access_token


def _valid_access_token(connection):
    if connection.token_expiry <= timezone.now() + timedelta(minutes=2):
        return _refresh_access_token(connection)
    return connection.access_token


def _headers(connection):
    return {"Authorization": f"Bearer {_valid_access_token(connection)}", "Content-Type": "application/json"}


def _event_payload(appointment):
    return {
        "summary": f"RDV — {appointment.patient}",
        "description": appointment.reason or "",
        "start": {"dateTime": appointment.start_time.isoformat()},
        "end": {"dateTime": appointment.end_time.isoformat()},
    }


def upsert_event(connection, appointment):
    """Crée l'événement Google correspondant au RDV, ou le met à jour s'il existe déjà. Renvoie l'event id."""
    if appointment.google_event_id:
        url = f"{CALENDAR_API_BASE}/calendars/{connection.calendar_id}/events/{appointment.google_event_id}"
        resp = requests.patch(url, headers=_headers(connection), json=_event_payload(appointment), timeout=10)
        if resp.ok:
            return resp.json()["id"]
        if resp.status_code != 404:
            raise GoogleCalendarError(f"Mise à jour d'événement échouée : {resp.text}")
        # 404 : l'événement a été supprimé côté Google, on le recrée ci-dessous.

    url = f"{CALENDAR_API_BASE}/calendars/{connection.calendar_id}/events"
    resp = requests.post(url, headers=_headers(connection), json=_event_payload(appointment), timeout=10)
    if not resp.ok:
        raise GoogleCalendarError(f"Création d'événement échouée : {resp.text}")
    return resp.json()["id"]


def delete_event(connection, appointment):
    if not appointment.google_event_id:
        return
    url = f"{CALENDAR_API_BASE}/calendars/{connection.calendar_id}/events/{appointment.google_event_id}"
    resp = requests.delete(url, headers=_headers(connection), timeout=10)
    if resp.status_code not in (200, 204, 404, 410):
        raise GoogleCalendarError(f"Suppression d'événement échouée : {resp.text}")


def get_busy_periods(connection, time_min, time_max):
    """Renvoie la liste des créneaux occupés (dict avec 'start'/'end' ISO) sur l'agenda Google du praticien."""
    url = f"{CALENDAR_API_BASE}/freeBusy"
    payload = {
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat(),
        "items": [{"id": connection.calendar_id}],
    }
    resp = requests.post(url, headers=_headers(connection), json=payload, timeout=10)
    if not resp.ok:
        raise GoogleCalendarError(f"Requête freebusy échouée : {resp.text}")
    data = resp.json()
    return data.get("calendars", {}).get(connection.calendar_id, {}).get("busy", [])


def revoke(connection):
    """Révoque le token auprès de Google (best-effort, ne bloque pas la déconnexion locale en cas d'échec)."""
    try:
        requests.post(
            "https://oauth2.googleapis.com/revoke",
            params={"token": connection.refresh_token},
            headers={"content-type": "application/x-www-form-urlencoded"},
            timeout=10,
        )
    except requests.RequestException:
        pass
