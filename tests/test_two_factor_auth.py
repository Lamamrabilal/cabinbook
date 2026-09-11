import pytest
import pyotp
from rest_framework.test import APIClient


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="2fa@example.com", email="2fa@example.com", password="testpass123",
    )


@pytest.fixture
def client_(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


class TestTwoFactorSetupFlow:
    def test_setup_returns_secret_and_otpauth_url(self, client_, user):
        res = client_.post("/api/accounts/2fa/setup/")
        assert res.status_code == 200
        assert "secret" in res.data
        assert res.data["otpauth_url"].startswith("otpauth://totp/")

        user.refresh_from_db()
        assert user.otp_secret == res.data["secret"]
        assert user.otp_enabled is False

    def test_confirm_with_valid_code_enables_2fa(self, client_, user):
        setup_res = client_.post("/api/accounts/2fa/setup/")
        secret = setup_res.data["secret"]
        code = pyotp.TOTP(secret).now()

        res = client_.post("/api/accounts/2fa/confirm/", {"code": code})
        assert res.status_code == 200, res.data

        user.refresh_from_db()
        assert user.otp_enabled is True

    def test_confirm_with_invalid_code_fails(self, client_, user):
        client_.post("/api/accounts/2fa/setup/")
        res = client_.post("/api/accounts/2fa/confirm/", {"code": "000000"})
        assert res.status_code == 400

        user.refresh_from_db()
        assert user.otp_enabled is False

    def test_disable_requires_valid_code(self, client_, user):
        setup_res = client_.post("/api/accounts/2fa/setup/")
        secret = setup_res.data["secret"]
        client_.post("/api/accounts/2fa/confirm/", {"code": pyotp.TOTP(secret).now()})

        res_bad = client_.post("/api/accounts/2fa/disable/", {"code": "000000"})
        assert res_bad.status_code == 400
        user.refresh_from_db()
        assert user.otp_enabled is True

        res_ok = client_.post("/api/accounts/2fa/disable/", {"code": pyotp.TOTP(secret).now()})
        assert res_ok.status_code == 200
        user.refresh_from_db()
        assert user.otp_enabled is False
        assert user.otp_secret == ""


class TestLoginWithTwoFactor:
    def _enable_2fa(self, client_, user):
        setup_res = client_.post("/api/accounts/2fa/setup/")
        secret = setup_res.data["secret"]
        client_.post("/api/accounts/2fa/confirm/", {"code": pyotp.TOTP(secret).now()})
        return secret

    def test_login_without_2fa_enabled_works_normally(self, db, user):
        client = APIClient()
        res = client.post("/api/auth/token/", {"email": user.email, "password": "testpass123"}, format="json")
        assert res.status_code == 200

    def test_login_with_2fa_enabled_requires_otp_code(self, client_, user):
        self._enable_2fa(client_, user)
        anon_client = APIClient()
        res = anon_client.post(
            "/api/auth/token/", {"email": user.email, "password": "testpass123"}, format="json"
        )
        assert res.status_code == 401
        assert res.data["requires_otp"] is True

    def test_login_with_2fa_and_correct_code_succeeds(self, client_, user):
        secret = self._enable_2fa(client_, user)
        anon_client = APIClient()
        res = anon_client.post(
            "/api/auth/token/",
            {"email": user.email, "password": "testpass123", "otp_code": pyotp.TOTP(secret).now()},
            format="json",
        )
        assert res.status_code == 200

    def test_login_with_2fa_and_wrong_code_fails(self, client_, user):
        self._enable_2fa(client_, user)
        anon_client = APIClient()
        res = anon_client.post(
            "/api/auth/token/",
            {"email": user.email, "password": "testpass123", "otp_code": "000000"},
            format="json",
        )
        assert res.status_code == 401

    def test_login_with_2fa_and_wrong_password_does_not_leak_otp_requirement(self, client_, user):
        self._enable_2fa(client_, user)
        anon_client = APIClient()
        res = anon_client.post(
            "/api/auth/token/", {"email": user.email, "password": "wrongpassword"}, format="json"
        )
        assert res.status_code == 401
        assert "requires_otp" not in res.data
