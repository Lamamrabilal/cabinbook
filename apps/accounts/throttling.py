from rest_framework.throttling import SimpleRateThrottle


class BruteForceRateThrottle(SimpleRateThrottle):
    """
    Throttle de base pour les endpoints exposés à la force brute (mot de
    passe, code 2FA, réinitialisation de mot de passe) : 5 tentatives par
    adresse IP, puis blocage de 15 minutes. Sous-classée une fois par
    endpoint (via `scope`) pour que les compteurs ne se mélangent pas entre
    connexion, 2FA et reset de mot de passe.
    """
    rate = "5/15min"  # valeur informative — la fenêtre réelle est fixée ci-dessous
    num_requests = 5
    duration = 15 * 60

    def parse_rate(self, rate):
        return self.num_requests, self.duration

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class LoginRateThrottle(BruteForceRateThrottle):
    scope = "login"


class TwoFactorRateThrottle(BruteForceRateThrottle):
    scope = "two_factor"


class PasswordResetRateThrottle(BruteForceRateThrottle):
    scope = "password_reset"
