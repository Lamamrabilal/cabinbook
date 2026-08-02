from rest_framework import serializers
from apps.accounts.models import User, Practitioner, Patient


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "plan", "is_subscription_active", "created_at"]
        read_only_fields = ["plan", "is_subscription_active", "created_at"]


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
    class Meta:
        model = Practitioner
        fields = [
            "id", "first_name", "last_name", "specialty",
            "phone", "email", "booking_page_slug", "is_active", "created_at"
        ]
        read_only_fields = ["created_at"]

    def validate_booking_page_slug(self, value):
        qs = Practitioner.objects.filter(booking_page_slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ce slug est déjà utilisé.")
        return value

    def validate(self, attrs):
        """Vérifier que le plan autorise le nombre de praticiens."""
        request = self.context.get("request")
        if request and not self.instance:
            user = request.user
            current_count = user.practitioners.filter(is_active=True).count()
            if current_count >= user.max_practitioners:
                raise serializers.ValidationError(
                    f"Votre plan {user.plan} est limité à {user.max_practitioners} praticien(s). "
                    "Passez au plan Cabinet pour en ajouter davantage."
                )
        return attrs


class PatientSerializer(serializers.ModelSerializer):
    practitioner_name = serializers.CharField(source="practitioner.__str__", read_only=True)

    class Meta:
        model = Patient
        fields = ["id", "first_name", "last_name", "email", "phone", "notes", "practitioner_name", "created_at"]
        read_only_fields = ["created_at", "practitioner_name"]
