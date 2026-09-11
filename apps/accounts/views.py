import csv
import io
import logging
from rest_framework import generics, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import MultiPartParser
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.shortcuts import redirect
from django.db import IntegrityError, transaction
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils.crypto import get_random_string
from django.conf import settings

from apps.accounts.models import User, Practitioner, Patient, Room
from apps.accounts.permissions import IsAccountOwner
from apps.accounts.serializers import (
    UserSerializer,
    RegisterSerializer,
    PractitionerSerializer,
    PatientSerializer,
    StaffAccountSerializer,
    RoomSerializer,
)
from apps.accounts.throttling import LoginRateThrottle, TwoFactorRateThrottle, PasswordResetRateThrottle

logger = logging.getLogger(__name__)


class RegisterView(generics.CreateAPIView):
    """Inscription d'un nouvel utilisateur."""
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class MeView(generics.RetrieveUpdateAPIView):
    """Profil de l'utilisateur connecté."""
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PractitionerViewSet(viewsets.ModelViewSet):
    """Gestion des praticiens du compte."""
    serializer_class = PractitionerSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Practitioner.objects.filter(owner=self.request.user.effective_owner)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user.effective_owner)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        practitioner = self.get_object()
        practitioner.is_active = False
        practitioner.save(update_fields=["is_active"])
        return Response({"status": "désactivé"})


class PatientViewSet(viewsets.ModelViewSet):
    """Gestion des patients d'un praticien."""
    serializer_class = PatientSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        qs = Patient.objects.filter(practitioner__owner=self.request.user.effective_owner, is_active=True)
        # Filtre par praticien optionnel
        practitioner_id = self.request.query_params.get("practitioner")
        if practitioner_id:
            qs = qs.filter(practitioner_id=practitioner_id)
        return qs.select_related("practitioner")

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        """Desactive un patient (suppression douce) sans effacer son historique de RDV."""
        patient = self.get_object()
        patient.is_active = False
        patient.save(update_fields=["is_active"])
        return Response({"message": "Patient desactive."})

    @action(detail=False, methods=["post"], parser_classes=[MultiPartParser])
    def import_csv(self, request):
        """
        POST /api/accounts/patients/import_csv/
        Payload (multipart/form-data) : file=<CSV>, practitioner=<id>
        Colonnes reconnues (insensible a la casse/accents, alias FR ou EN) :
        prenom/first_name (requis), nom/last_name (requis), email, telephone/phone, notes.
        Delimiteur (, ou ;) et encodage (UTF-8 ou latin-1) detectes automatiquement.
        Chaque ligne est importee independamment : une ligne invalide ou en doublon
        (meme praticien + meme email) est ignoree sans bloquer les autres.
        """
        practitioner_id = request.data.get("practitioner")
        if not practitioner_id:
            return Response({"error": "Le champ practitioner est requis."}, status=400)
        try:
            practitioner = Practitioner.objects.get(
                pk=practitioner_id, owner=request.user.effective_owner
            )
        except Practitioner.DoesNotExist:
            return Response({"error": "Praticien introuvable."}, status=404)

        upload = request.FILES.get("file")
        if not upload:
            return Response({"error": "Aucun fichier fourni."}, status=400)

        raw = upload.read()
        try:
            decoded = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            decoded = raw.decode("latin-1")

        try:
            dialect = csv.Sniffer().sniff(decoded[:2000], delimiters=",;")
        except csv.Error:
            dialect = csv.excel
        reader = csv.DictReader(io.StringIO(decoded), dialect=dialect)

        field_aliases = {
            "first_name": {"first_name", "prenom", "firstname"},
            "last_name": {"last_name", "nom", "lastname"},
            "email": {"email", "e-mail", "mail"},
            "phone": {"phone", "telephone", "tel"},
            "notes": {"notes", "note", "commentaire"},
        }

        def normalize(s):
            s = (s or "").strip().lower()
            for accented, plain in (("é", "e"), ("è", "e"), ("ê", "e")):
                s = s.replace(accented, plain)
            return s

        header_map = {}
        for field, aliases in field_aliases.items():
            for h in (reader.fieldnames or []):
                if normalize(h) in aliases:
                    header_map[field] = h
                    break

        if "first_name" not in header_map or "last_name" not in header_map:
            return Response(
                {"error": "Colonnes 'prenom' et 'nom' introuvables dans le fichier."},
                status=400,
            )

        MAX_ROWS = 2000
        created, skipped, errors = 0, 0, []
        for i, row in enumerate(reader, start=1):
            if i > MAX_ROWS:
                errors.append(f"Import limité à {MAX_ROWS} lignes : le reste du fichier a été ignoré.")
                break

            first_name = (row.get(header_map["first_name"]) or "").strip()
            last_name = (row.get(header_map["last_name"]) or "").strip()
            email = (row.get(header_map.get("email"), "") or "").strip().lower()
            phone = (row.get(header_map.get("phone"), "") or "").strip()
            notes = (row.get(header_map.get("notes"), "") or "").strip()

            if not first_name or not last_name:
                skipped += 1
                errors.append(f"Ligne {i} : prénom/nom manquant, ignorée.")
                continue

            if email and Patient.objects.filter(practitioner=practitioner, email=email).exists():
                skipped += 1
                errors.append(f"Ligne {i} : doublon ({email}), ignorée.")
                continue

            try:
                with transaction.atomic():
                    Patient.objects.create(
                        practitioner=practitioner, first_name=first_name, last_name=last_name,
                        email=email, phone=phone, notes=notes,
                    )
                created += 1
            except IntegrityError:
                skipped += 1
                errors.append(f"Ligne {i} : doublon, ignorée.")

        return Response({"created": created, "skipped": skipped, "errors": errors[:50]})

    def perform_create(self, serializer):
        # Vérifier que le praticien appartient bien à cet utilisateur
        practitioner = serializer.validated_data["practitioner"]
        if practitioner.owner != self.request.user.effective_owner:
            raise PermissionDenied("Praticien non autorisé.")
        serializer.save()


class StaffAccountViewSet(viewsets.ModelViewSet):
    """
    Gestion des comptes secrétaire (accès restreint) du cabinet.
    Réservé au titulaire du compte — un compte secrétaire ne peut ni consulter
    ni gérer d'autres comptes secrétaire (voir IsAccountOwner).
    """
    serializer_class = StaffAccountSerializer
    permission_classes = [IsAuthenticated, IsAccountOwner]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return User.objects.filter(owner_account=self.request.user, role=User.ROLE_SECRETARY)

    def perform_create(self, serializer):
        owner = self.request.user
        if owner.staff_members.count() >= owner.max_staff:
            raise PermissionDenied(
                f"Limite de {owner.max_staff} compte(s) secrétaire atteinte pour le plan {owner.plan}."
            )
        temp_password = get_random_string(12)
        email = serializer.validated_data["email"]
        user = serializer.save(username=email, role=User.ROLE_SECRETARY, owner_account=owner)
        user.set_password(temp_password)
        user.save(update_fields=["password"])
        try:
            from apps.notifications.services import EmailService
            EmailService.send_staff_account_created(user, owner, temp_password)
        except Exception:
            logger.exception("Échec de l'email de création de compte secrétaire pour %s", user.email)

    def perform_update(self, serializer):
        """
        Bloque la réactivation (is_active False → True) au-delà du plafond du
        plan — sans ça, un titulaire pourrait réactiver un compte secrétaire
        désactivé sans jamais repasser par la vérification de perform_create.
        """
        instance = serializer.instance
        will_be_active = serializer.validated_data.get("is_active", instance.is_active)
        if will_be_active and not instance.is_active:
            owner = self.request.user
            if owner.staff_members.count() >= owner.max_staff:
                raise PermissionDenied(
                    f"Limite de {owner.max_staff} compte(s) secrétaire atteinte pour le plan {owner.plan}."
                )
        serializer.save()

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        staff = self.get_object()
        staff.is_active = False
        staff.save(update_fields=["is_active"])
        return Response({"status": "désactivé"})


class RoomViewSet(viewsets.ModelViewSet):
    """Salles du cabinet (plan Cabinet). Un compte secrétaire peut les consulter
    (pour en assigner une à un RDV) mais seul le titulaire peut en créer/supprimer."""
    serializer_class = RoomSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsAccountOwner()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return Room.objects.filter(owner=self.request.user.effective_owner)

    def perform_create(self, serializer):
        owner = self.request.user
        max_rooms = 10 if owner.plan == "cabinet" else 0
        if owner.rooms.filter(is_active=True).count() >= max_rooms:
            raise PermissionDenied(
                "La gestion de salles est réservée au plan Cabinet." if max_rooms == 0
                else f"Limite de {max_rooms} salles atteinte."
            )
        serializer.save(owner=owner)

    def perform_update(self, serializer):
        """Bloque la réactivation (is_active False → True) au-delà du plafond du plan."""
        instance = serializer.instance
        will_be_active = serializer.validated_data.get("is_active", instance.is_active)
        if will_be_active and not instance.is_active:
            owner = self.request.user.effective_owner
            max_rooms = 10 if owner.plan == "cabinet" else 0
            if owner.rooms.filter(is_active=True).count() >= max_rooms:
                raise PermissionDenied(
                    "La gestion de salles est réservée au plan Cabinet." if max_rooms == 0
                    else f"Limite de {max_rooms} salles atteinte."
                )
        serializer.save()


class PasswordResetRequestView(generics.GenericAPIView):
    """
    POST /api/accounts/password-reset/
    Envoie un email avec un lien de reinitialisation si le compte existe.
    Ne revele jamais si l'email existe ou non (protection contre l'enumeration).
    """
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        from apps.accounts.models import User
        from apps.notifications.services import EmailService

        email = request.data.get("email", "").strip().lower()
        user = User.objects.filter(email=email).first()

        if user:
            token_generator = PasswordResetTokenGenerator()
            token = token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"
            try:
                EmailService.send_password_reset(user, reset_url)
            except Exception:
                pass  # Ne jamais bloquer/reveler un echec d'envoi au client

        return Response({
            "message": "Si un compte existe avec cet email, un lien de reinitialisation a ete envoye."
        })


class PasswordResetConfirmView(generics.GenericAPIView):
    """
    POST /api/accounts/password-reset-confirm/
    Valide le token et applique le nouveau mot de passe.
    """
    permission_classes = [AllowAny]
    throttle_classes = [PasswordResetRateThrottle]

    def post(self, request):
        from apps.accounts.models import User

        uid = request.data.get("uid", "")
        token = request.data.get("token", "")
        new_password = request.data.get("password", "")

        if not new_password or len(new_password) < 8:
            return Response({"error": "Le mot de passe doit contenir au moins 8 caracteres."}, status=400)

        try:
            user_id = force_str(urlsafe_base64_decode(uid))
            user = User.objects.get(pk=user_id)
        except (User.DoesNotExist, ValueError, TypeError, OverflowError):
            return Response({"error": "Lien de reinitialisation invalide."}, status=400)

        token_generator = PasswordResetTokenGenerator()
        if not token_generator.check_token(user, token):
            return Response({"error": "Lien de reinitialisation invalide ou expire."}, status=400)

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response({"message": "Mot de passe reinitialise avec succes."})


class ContactMessageView(generics.GenericAPIView):
    """POST /api/accounts/contact/ — recoit un message du formulaire de contact public."""
    permission_classes = [AllowAny]

    def post(self, request):
        from apps.notifications.services import EmailService

        name = request.data.get("name", "").strip()
        email = request.data.get("email", "").strip()
        message = request.data.get("message", "").strip()

        if not name or not email or not message:
            return Response({"error": "Tous les champs sont requis."}, status=400)

        try:
            EmailService.send_contact_message(name, email, message)
        except Exception:
            return Response({"error": "Impossible d'envoyer le message pour le moment."}, status=500)

        return Response({"message": "Votre message a bien ete envoye. Nous vous repondrons rapidement."})


# ── Authentification à deux facteurs (TOTP) ──────────────
class TwoFactorSetupView(generics.GenericAPIView):
    """POST /api/accounts/2fa/setup/ — génère un nouveau secret TOTP (non activé)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        import pyotp
        user = request.user
        secret = pyotp.random_base32()
        user.otp_secret = secret
        user.otp_enabled = False
        user.save(update_fields=["otp_secret", "otp_enabled"])
        otpauth_url = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="CabinBook")
        return Response({"secret": secret, "otpauth_url": otpauth_url})


class TwoFactorConfirmView(generics.GenericAPIView):
    """POST /api/accounts/2fa/confirm/ — valide le premier code et active la 2FA."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorRateThrottle]

    def post(self, request):
        from apps.accounts.otp import verify_totp
        user = request.user
        if not user.otp_secret:
            return Response({"error": "Aucune configuration 2FA en cours. Relancez /2fa/setup/."}, status=400)
        if not verify_totp(user, request.data.get("code", "")):
            return Response({"error": "Code invalide."}, status=400)
        user.otp_enabled = True
        user.save(update_fields=["otp_enabled"])
        return Response({"message": "Authentification à deux facteurs activée."})


class TwoFactorDisableView(generics.GenericAPIView):
    """POST /api/accounts/2fa/disable/ — désactive la 2FA (code de vérification requis)."""
    permission_classes = [IsAuthenticated]
    throttle_classes = [TwoFactorRateThrottle]

    def post(self, request):
        from apps.accounts.otp import verify_totp
        user = request.user
        if not user.otp_enabled or not verify_totp(user, request.data.get("code", "")):
            return Response({"error": "Code invalide."}, status=400)
        user.otp_enabled = False
        user.otp_secret = ""
        user.save(update_fields=["otp_enabled", "otp_secret"])
        return Response({"message": "Authentification à deux facteurs désactivée."})


# ── Synchro Google Calendar ───────────────────────────────
class GoogleCalendarConnectView(generics.GenericAPIView):
    """GET /api/accounts/calendar/google/connect/?practitioner=<id> — URL de connexion OAuth."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts import google_calendar

        practitioner_id = request.query_params.get("practitioner")
        try:
            practitioner = Practitioner.objects.get(pk=practitioner_id, owner=request.user.effective_owner)
        except (Practitioner.DoesNotExist, ValueError, TypeError):
            return Response({"error": "Praticien introuvable."}, status=404)

        return Response({"authorization_url": google_calendar.build_authorization_url(practitioner)})


class GoogleCalendarCallbackView(generics.GenericAPIView):
    """
    GET /api/accounts/calendar/google/callback/ — Google redirige ici le
    navigateur après consentement. Public (AllowAny) : l'identité du
    praticien est portée par le paramètre `state` signé généré à l'étape
    connect/, pas par la session/cookie (qui peut avoir expiré pendant que
    l'utilisateur était sur l'écran de consentement Google).
    """
    permission_classes = [AllowAny]

    def get(self, request):
        from apps.accounts import google_calendar
        from apps.accounts.models import GoogleCalendarConnection

        code = request.query_params.get("code")
        state = request.query_params.get("state")
        error = request.query_params.get("error")

        if error or not code or not state:
            return redirect(f"{settings.FRONTEND_URL}/?calendar=error")

        practitioner_id = google_calendar.parse_state(state)
        if not practitioner_id:
            return redirect(f"{settings.FRONTEND_URL}/?calendar=error")

        try:
            practitioner = Practitioner.objects.get(pk=practitioner_id)
        except Practitioner.DoesNotExist:
            return redirect(f"{settings.FRONTEND_URL}/?calendar=error")

        try:
            tokens = google_calendar.exchange_code_for_tokens(code)
            google_email = google_calendar.fetch_google_email(tokens["access_token"])
        except google_calendar.GoogleCalendarError:
            logger.exception("Echec de l'echange OAuth Google Calendar pour praticien %s", practitioner_id)
            return redirect(f"{settings.FRONTEND_URL}/?calendar=error")

        from datetime import timedelta
        from django.utils import timezone as dj_timezone

        GoogleCalendarConnection.objects.update_or_create(
            practitioner=practitioner,
            defaults={
                "google_email": google_email,
                "access_token": tokens["access_token"],
                "refresh_token": tokens.get("refresh_token") or "",
                "token_expiry": dj_timezone.now() + timedelta(seconds=tokens.get("expires_in", 3600)),
            },
        )
        return redirect(f"{settings.FRONTEND_URL}/?calendar=connected")


class GoogleCalendarDisconnectView(generics.GenericAPIView):
    """POST /api/accounts/calendar/google/disconnect/ — Payload: { practitioner }."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from apps.accounts import google_calendar
        from apps.accounts.models import GoogleCalendarConnection

        practitioner_id = request.data.get("practitioner")
        try:
            connection = GoogleCalendarConnection.objects.select_related("practitioner").get(
                practitioner_id=practitioner_id, practitioner__owner=request.user.effective_owner
            )
        except GoogleCalendarConnection.DoesNotExist:
            return Response({"error": "Aucune connexion Google Calendar pour ce praticien."}, status=404)

        google_calendar.revoke(connection)
        connection.delete()
        return Response({"message": "Google Calendar déconnecté."})


# ── Authentification par cookies httpOnly ────────────────
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from django.conf import settings as django_settings

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
COOKIE_SECURE = not django_settings.DEBUG
COOKIE_SAMESITE = "Lax"


def _set_auth_cookies(response, access, refresh=None):
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE, path="/", max_age=60 * 60,
    )
    if refresh:
        response.set_cookie(
            REFRESH_COOKIE, refresh, httponly=True, secure=COOKIE_SECURE,
            samesite=COOKIE_SAMESITE, path="/", max_age=60 * 60 * 24 * 7,
        )


class CookieTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]

    def post(self, request, *args, **kwargs):
        from apps.accounts.otp import verify_totp

        email = request.data.get("email", "")
        password = request.data.get("password", "")
        candidate = User.objects.filter(email=email).first()
        if candidate and candidate.otp_enabled and candidate.check_password(password):
            otp_code = request.data.get("otp_code", "")
            if not verify_totp(candidate, otp_code):
                return Response(
                    {"requires_otp": True, "detail": "Code de vérification à deux facteurs requis."},
                    status=401,
                )

        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access = response.data.pop("access", None)
            refresh = response.data.pop("refresh", None)
            _set_auth_cookies(response, access, refresh)
        return response


class CookieTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get(REFRESH_COOKIE)
        if not refresh_token:
            return Response({"detail": "Aucun token de rafraichissement."}, status=401)
        request.data["refresh"] = refresh_token
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            access = response.data.pop("access", None)
            _set_auth_cookies(response, access)
        return response


class LogoutView(generics.GenericAPIView):
    permission_classes = [AllowAny]

    def post(self, request):
        response = Response({"message": "Deconnecte avec succes."})
        response.delete_cookie(ACCESS_COOKIE, path="/")
        response.delete_cookie(REFRESH_COOKIE, path="/")
        return response
