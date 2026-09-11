"""Champs de modele personnalises pour donnees sensibles."""
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models


def _get_fernet():
    return Fernet(settings.FIELD_ENCRYPTION_KEY.encode() if isinstance(settings.FIELD_ENCRYPTION_KEY, str) else settings.FIELD_ENCRYPTION_KEY)


class EncryptedCharField(models.CharField):
    """
    CharField dont la valeur est chiffree (Fernet) avant stockage en base,
    et dechiffree automatiquement a la lecture. Transparent pour le reste
    du code (serializers, vues) : on manipule toujours la valeur en clair
    en Python, seul le contenu en base de donnees est chiffre.
    """

    def __init__(self, *args, **kwargs):
        # Le texte chiffre est plus long que le texte original : on augmente
        # la longueur max de stockage sans changer la validation cote form/API.
        self.plain_max_length = kwargs.get("max_length", 255)
        kwargs["max_length"] = max(500, self.plain_max_length * 4)
        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        kwargs["max_length"] = self.plain_max_length
        return name, path, args, kwargs

    def _encrypt(self, value):
        if value in (None, ""):
            return value
        return _get_fernet().encrypt(value.encode()).decode()

    def _decrypt(self, value):
        if value in (None, ""):
            return value
        try:
            return _get_fernet().decrypt(value.encode()).decode()
        except (InvalidToken, ValueError):
            # Valeur pre-existante non chiffree, ou cle invalide : on la
            # retourne telle quelle plutot que de planter, pour rester
            # tolerant lors d'une migration progressive.
            return value

    def from_db_value(self, value, expression, connection):
        return self._decrypt(value)

    def to_python(self, value):
        if isinstance(value, str):
            return value
        return super().to_python(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return self._encrypt(value)
