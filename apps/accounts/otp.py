"""Aide à la vérification TOTP (authentification à deux facteurs)."""
import pyotp


def verify_totp(user, code):
    """Vérifie un code à 6 chiffres contre le secret TOTP de l'utilisateur.
    Tolère un léger décalage d'horloge (fenêtre de ±30s)."""
    if not user.otp_secret or not code:
        return False
    return pyotp.TOTP(user.otp_secret).verify(str(code).strip(), valid_window=1)
