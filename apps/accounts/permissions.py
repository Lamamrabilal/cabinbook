from rest_framework.permissions import BasePermission


class IsAccountOwner(BasePermission):
    """Autorise uniquement les comptes titulaires — exclut les comptes secrétaire.

    Utilisé pour les actions sensibles qu'un compte secrétaire ne doit jamais
    pouvoir déclencher : gestion de l'abonnement SaaS, gestion des autres comptes
    secrétaire.
    """
    message = "Cette action est réservée au titulaire du compte."

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role == user.ROLE_OWNER)
