from rest_framework import generics, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny

from apps.accounts.models import Practitioner, Patient
from apps.accounts.serializers import (
    UserSerializer,
    RegisterSerializer,
    PractitionerSerializer,
    PatientSerializer,
)


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
        return Practitioner.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

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
        qs = Patient.objects.filter(practitioner__owner=self.request.user)
        # Filtre par praticien optionnel
        practitioner_id = self.request.query_params.get("practitioner")
        if practitioner_id:
            qs = qs.filter(practitioner_id=practitioner_id)
        return qs.select_related("practitioner")

    def perform_create(self, serializer):
        # Vérifier que le praticien appartient bien à cet utilisateur
        practitioner = serializer.validated_data["practitioner"]
        if practitioner.owner != self.request.user:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Praticien non autorisé.")
        serializer.save()
