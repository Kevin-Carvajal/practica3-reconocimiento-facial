"""Configuración para ejecutar las pruebas sin PostgreSQL.

Usa SQLite en memoria, así las pruebas corren en cualquier equipo:
    python manage.py test --settings=config.settings_test
"""
from .settings import *  # noqa: F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}
