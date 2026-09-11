import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def clear_throttle_cache():
    """
    Le cache par défaut (Redis) est aussi utilisé par le rate limiting DRF
    sur les endpoints sensibles à la force brute (connexion, 2FA, reset de
    mot de passe). Sans ce nettoyage, les compteurs de tentatives persistent
    entre les tests (et entre les runs) sur la même IP de test, ce qui ferait
    échouer par erreur des tests sans rapport avec le rate limiting.
    """
    cache.clear()
