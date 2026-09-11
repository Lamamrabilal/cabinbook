import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient


@pytest.fixture
def user(db, django_user_model):
    return django_user_model.objects.create_user(
        username="kine.csv@example.com", email="kine.csv@example.com",
        password="testpass123", plan="pro",
    )


@pytest.fixture
def practitioner(db, user):
    from apps.accounts.models import Practitioner
    return Practitioner.objects.create(
        owner=user, first_name="Jean", last_name="Dupont",
        specialty="kine", booking_page_slug="jean-dupont-csv-test",
    )


@pytest.fixture
def other_practitioner(db, django_user_model):
    from apps.accounts.models import Practitioner
    other = django_user_model.objects.create_user(
        username="autre@example.com", email="autre@example.com", password="testpass123",
    )
    return Practitioner.objects.create(
        owner=other, first_name="Alice", last_name="Martin",
        specialty="osteo", booking_page_slug="alice-martin-csv-test",
    )


@pytest.fixture
def client_(user):
    c = APIClient()
    c.force_authenticate(user=user)
    return c


def make_csv_file(content, name="patients.csv"):
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


class TestPatientCsvImport:
    def test_import_creates_patients(self, client_, practitioner):
        csv_content = (
            "prenom,nom,email,telephone\n"
            "Marie,Martin,marie@example.com,0611111111\n"
            "Paul,Durand,paul@example.com,0622222222\n"
        )
        res = client_.post(
            "/api/accounts/patients/import_csv/",
            {"practitioner": practitioner.id, "file": make_csv_file(csv_content)},
            format="multipart",
        )
        assert res.status_code == 200, res.data
        assert res.data["created"] == 2
        assert res.data["skipped"] == 0

        from apps.accounts.models import Patient
        assert Patient.objects.filter(practitioner=practitioner).count() == 2

    def test_import_handles_semicolon_delimiter_and_english_headers(self, client_, practitioner):
        csv_content = "first_name;last_name;email\nMarie;Martin;marie2@example.com\n"
        res = client_.post(
            "/api/accounts/patients/import_csv/",
            {"practitioner": practitioner.id, "file": make_csv_file(csv_content)},
            format="multipart",
        )
        assert res.status_code == 200, res.data
        assert res.data["created"] == 1

    def test_import_skips_duplicates_and_missing_names(self, client_, practitioner):
        from apps.accounts.models import Patient
        Patient.objects.create(
            practitioner=practitioner, first_name="Marie", last_name="Martin",
            email="marie3@example.com",
        )
        csv_content = (
            "prenom,nom,email\n"
            "Marie,Martin,marie3@example.com\n"  # doublon
            ",Sansprenom,x@example.com\n"          # prenom manquant
            "Paul,Durand,paul3@example.com\n"      # valide
        )
        res = client_.post(
            "/api/accounts/patients/import_csv/",
            {"practitioner": practitioner.id, "file": make_csv_file(csv_content)},
            format="multipart",
        )
        assert res.status_code == 200, res.data
        assert res.data["created"] == 1
        assert res.data["skipped"] == 2
        assert len(res.data["errors"]) == 2

    def test_import_rejects_unrecognized_columns(self, client_, practitioner):
        csv_content = "colonne_a,colonne_b\nfoo,bar\n"
        res = client_.post(
            "/api/accounts/patients/import_csv/",
            {"practitioner": practitioner.id, "file": make_csv_file(csv_content)},
            format="multipart",
        )
        assert res.status_code == 400

    def test_import_rejects_other_owners_practitioner(self, client_, other_practitioner):
        csv_content = "prenom,nom\nMarie,Martin\n"
        res = client_.post(
            "/api/accounts/patients/import_csv/",
            {"practitioner": other_practitioner.id, "file": make_csv_file(csv_content)},
            format="multipart",
        )
        assert res.status_code == 404

    def test_import_requires_file(self, client_, practitioner):
        res = client_.post(
            "/api/accounts/patients/import_csv/",
            {"practitioner": practitioner.id},
            format="multipart",
        )
        assert res.status_code == 400
