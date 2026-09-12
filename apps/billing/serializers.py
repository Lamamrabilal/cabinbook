from rest_framework import serializers
from apps.billing.models import Invoice


class InvoiceSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    patient_name = serializers.SerializerMethodField()
    practitioner_name = serializers.CharField(source="appointment.practitioner.__str__", read_only=True)
    appointment_date = serializers.DateTimeField(source="appointment.start_time", read_only=True)

    class Meta:
        model = Invoice
        fields = [
            "id", "appointment", "amount_cents", "status", "status_display",
            "patient_name", "practitioner_name", "appointment_date", "paid_at", "refunded_at", "created_at",
        ]
        read_only_fields = ["status", "paid_at", "refunded_at", "created_at"]

    def get_patient_name(self, obj):
        p = obj.appointment.patient
        return f"{p.first_name} {p.last_name}"

    def validate_appointment(self, appointment):
        request = self.context.get("request")
        if request and appointment.practitioner.owner != request.user.effective_owner:
            raise serializers.ValidationError("Ce rendez-vous n'appartient pas à un de vos praticiens.")
        return appointment

    def validate_amount_cents(self, value):
        if (
            self.instance
            and self.instance.status in (Invoice.STATUS_PAID, Invoice.STATUS_REFUNDED)
            and value != self.instance.amount_cents
        ):
            raise serializers.ValidationError("Impossible de modifier le montant d'une facture payée ou remboursée.")
        return value
