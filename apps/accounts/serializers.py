from rest_framework import serializers
from apps.accounts.models import User, Practitioner, Patient, Room


class UserSerializer(serializers.ModelSerializer):
    """Profil de l'utilisateur connecté. Pour un compte secrétaire, `plan` et
    `is_subscription_active` refletent le compte du titulaire (compte pour lequel
    il agit), pas les valeurs (vides) de sa propre ligne User."""
    plan = serializers.SerializerMethodField()
    is_subscription_active = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone",
            "role", "plan", "is_subscription_active", "owner_name", "otp_enabled", "created_at",
        ]
        read_only_fields = ["role", "plan", "is_subscription_active", "owner_name", "otp_enabled", "created_at"]

    def get_plan(self, obj):
        return obj.effective_owner.plan

    def get_is_subscription_active(self, obj):
        return obj.effective_owner.is_subscription_active

    def get_owner_name(self, obj):
        if obj.role != User.ROLE_SECRETARY or not obj.owner_account_id:
            return None
        owner = obj.owner_account
        return f"{owner.first_name} {owner.last_name}".strip() or owner.email


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["email", "first_name", "last_name", "phone", "password"]

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.username = validated_data["email"]
        user.set_password(password)
        user.save()
        return user


class PractitionerSerializer(serializers.ModelSerializer):
    google_calendar_connected = serializers.SerializerMethodField()
    google_calendar_email = serializers.SerializerMethodField()

    class Meta:
        model = Practitioner
        fields = [
            "id", "first_name", "last_name", "specialty",
            "phone", "email", "booking_page_slug", "city", "address", "is_listed",
            "consultation_price_cents", "deposit_amount_cents", "offers_teleconsultation", "is_active", "created_at",
            "google_calendar_connected", "google_calendar_email",
        ]
        read_only_fields = ["created_at"]

    def get_google_calendar_connected(self, obj):
        return hasattr(obj, "google_calendar_connection")

    def get_google_calendar_email(self, obj):
        connection = getattr(obj, "google_calendar_connection", None)
        return connection.google_email if connection else ""

    def validate_booking_page_slug(self, value):
        qs = Practitioner.objects.filter(booking_page_slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ce slug est déjà utilisé.")
        return value

    def validate(self, attrs):
        """
        Vérifier que le plan autorise le nombre de praticiens. S'applique à la
        création, mais aussi à une réactivation (is_active False → True) : sans
        ça, un titulaire au plafond pourrait désactiver un praticien, en créer
        un nouveau, puis réactiver l'ancien pour dépasser la limite de son plan.
        """
        request = self.context.get("request")
        if not request:
            return attrs
        will_be_active = attrs.get("is_active", getattr(self.instance, "is_active", True))
        was_active = self.instance.is_active if self.instance else False
        if will_be_active and not was_active:
            owner = request.user.effective_owner
            current_count = owner.practitioners.filter(is_active=True).count()
            if current_count >= owner.max_practitioners:
                raise serializers.ValidationError(
                    f"Votre plan {owner.plan} est limité à {owner.max_practitioners} praticien(s). "
                    "Passez au plan Cabinet pour en ajouter davantage."
                )
        return attrs


class PatientSerializer(serializers.ModelSerializer):
    practitioner_name = serializers.CharField(source="practitioner.__str__", read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "practitioner", "first_name", "last_name", "email", "phone", "carte_vitale_number", "notes", "practitioner_name", "created_at"]
        read_only_fields = ["created_at", "practitioner_name"]

    def validate_practitioner(self, practitioner):
        """
        Empêche de réassigner un patient (existant ou à la création) à un
        praticien d'un autre cabinet — sans ça, un titulaire pourrait, via un
        simple PATCH, faire apparaître un de ses patients (avec toutes ses
        données, y compris le numéro de carte vitale) dans la patientèle d'un
        autre compte.
        """
        request = self.context.get("request")
        if request and practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Praticien non autorisé.")
        return practitioner


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ["id", "name", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def validate_name(self, value):
        request = self.context.get("request")
        qs = Room.objects.filter(owner=request.user.effective_owner, name__iexact=value.strip())
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Une salle porte déjà ce nom.")
        return value.strip()


class StaffAccountSerializer(serializers.ModelSerializer):
    """Compte secrétaire — accès restreint au nom du titulaire (créé par lui)."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "is_active", "created_at"]
        read_only_fields = ["created_at"]

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Un compte existe déjà avec cet email.")
        return value
