from django.urls import path
from apps.accounts.public_views import PublicDirectoryView

urlpatterns = [
    path("", PublicDirectoryView.as_view(), name="public-directory"),
]
