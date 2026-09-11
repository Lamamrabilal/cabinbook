from django.db.models import Avg, Count, Q
from rest_framework import serializers as drf_serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from apps.accounts.models import Practitioner


class DirectoryPractitionerSerializer(drf_serializers.ModelSerializer):
    specialty_display = drf_serializers.CharField(source="get_specialty_display", read_only=True)
    average_rating = drf_serializers.SerializerMethodField()
    review_count = drf_serializers.SerializerMethodField()

    class Meta:
        model = Practitioner
        fields = [
            "id", "first_name", "last_name", "specialty", "specialty_display",
            "city", "booking_page_slug", "average_rating", "review_count",
        ]

    def get_average_rating(self, obj):
        avg = obj.review_agg_avg
        return round(avg, 1) if avg is not None else None

    def get_review_count(self, obj):
        return obj.review_agg_count


class PublicDirectoryView(ListAPIView):
    """
    GET /api/public/directory/?city=Paris&specialty=kine&q=dupont
    Annuaire public de recherche de praticiens (opt-in via Practitioner.is_listed).
    """
    serializer_class = DirectoryPractitionerSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self):
        qs = Practitioner.objects.filter(
            is_active=True, is_listed=True, owner__is_subscription_active=True,
        ).annotate(
            review_agg_avg=Avg("reviews__rating", filter=Q(reviews__is_hidden=False)),
            review_agg_count=Count("reviews", filter=Q(reviews__is_hidden=False)),
        )

        city = self.request.query_params.get("city")
        if city:
            qs = qs.filter(city__icontains=city)

        specialty = self.request.query_params.get("specialty")
        if specialty:
            qs = qs.filter(specialty=specialty)

        q = self.request.query_params.get("q")
        if q:
            qs = qs.filter(
                Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(city__icontains=q)
            )

        return qs.order_by("last_name")[:100]
