"""
Aucune limite de tentatives n'existait sur la connexion, la vérification du
code 2FA ou la réinitialisation de mot de passe : un attaquant pouvait tenter
un mot de passe, un code TOTP à 6 chiffres ou un token de reset à volonté,
sans aucun blocage. Ces endpoints sont maintenant limités à 5 tentatives par
adresse IP (voir apps/accounts/throttling.py), au-delà desquelles l'API
répond 429.
"""
import pyotp
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def user(db, django_user_model):
    u = django_user_model.objects.create_user(
        username="brute@example.com", email="brute@example.com",
        password="correct-password-123", plan="starter", is_subscription_active=True,
    )
    return u


class TestLoginRateLimiting:
    def test_sixth_login_attempt_is_throttled(self, user):
        client = APIClient()
        for _ in range(5):
            res = client.post("/api/auth/token/", {
                "email": user.email, "password": "wrong-password",
            }, format="json")
            assert res.status_code == 401

        res = client.post("/api/auth/token/", {
            "email": user.email, "password": "wrong-password",
        }, format="json")
        assert res.status_code == 429

    def test_correct_password_still_counts_towards_the_limit(self, user):
        client = APIClient()
        for _ in range(5):
            client.post("/api/auth/token/", {
                "email": user.email, "password": "correct-password-123",
            }, format="json")

        res = client.post("/api/auth/token/", {
            "email": user.email, "password": "correct-password-123",
        }, format="json")
        assert res.status_code == 429

    def test_different_ips_are_throttled_independently(self, user):
        client_a = APIClient(REMOTE_ADDR="10.0.0.1")
        client_b = APIClient(REMOTE_ADDR="10.0.0.2")
        for _ in range(5):
            client_a.post("/api/auth/token/", {
                "email": user.email, "password": "wrong-password",
            }, format="json")

        res_a = client_a.post("/api/auth/token/", {
            "email": user.email, "password": "wrong-password",
        }, format="json")
        assert res_a.status_code == 429

        res_b = client_b.post("/api/auth/token/", {
            "email": user.email, "password": "correct-password-123",
        }, format="json")
        assert res_b.status_code == 200


class TestTwoFactorRateLimiting:
    def test_sixth_2fa_confirm_attempt_is_throttled(self, user):
        user.otp_secret = pyotp.random_base32()
        user.save(update_fields=["otp_secret"])
        client = APIClient()
        client.force_authenticate(user=user)

        for _ in range(5):
            res = client.post("/api/accounts/2fa/confirm/", {"code": "000000"}, format="json")
            assert res.status_code == 400

        res = client.post("/api/accounts/2fa/confirm/", {"code": "000000"}, format="json")
        assert res.status_code == 429


class TestPasswordResetRateLimiting:
    def test_sixth_password_reset_request_is_throttled(self, user):
        client = APIClient()
        for _ in range(5):
            res = client.post("/api/accounts/password-reset/", {"email": user.email}, format="json")
            assert res.status_code == 200

        res = client.post("/api/accounts/password-reset/", {"email": user.email}, format="json")
        assert res.status_code == 429

    def test_sixth_password_reset_confirm_attempt_is_throttled(self, user):
        client = APIClient()
        for _ in range(5):
            res = client.post("/api/accounts/password-reset-confirm/", {
                "uid": "invalid", "token": "invalid", "password": "newpassword123",
            }, format="json")
            assert res.status_code == 400

        res = client.post("/api/accounts/password-reset-confirm/", {
            "uid": "invalid", "token": "invalid", "password": "newpassword123",
        }, format="json")
        assert res.status_code == 429
