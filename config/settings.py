"""
CUADRA - Operations Management System (Engineery Solutions S.A.S.)
Configuración de Django. Los valores sensibles vienen del archivo .env (NO se sube a Git).
"""
import os
from django.core.exceptions import ImproperlyConfigured
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY")
if not SECRET_KEY:
    raise ImproperlyConfigured("DJANGO_SECRET_KEY must be set.")
DEBUG = os.environ.get("DJANGO_DEBUG", "True") == "True"
# En la red local se agrega la IP del computador servidor, ej: 192.168.1.50
ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Módulos del sistema (ver Documento de Arquitectura)
    "apps.autenticacion",
    "apps.usuarios",      # Usuarios y Sedes
    "apps.catalogo",      # Productos, Tipos de producto, Proveedores
    "apps.inventario",
    "apps.pedidos",       # Mesas y Pedidos
    "apps.pagos",
    "apps.reportes",
    "apps.auditoria",     # Bitácora (transversal)
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.autenticacion.middleware.InactivityTimeoutMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.usuarios.context_processors.acting_mode",
                "apps.usuarios.context_processors.nav_menu",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ.get("DB_NAME", "cuadra_db"),
        "USER": os.environ.get("DB_USER", "cuadra_user"),
        "PASSWORD": os.environ.get("DB_PASSWORD", ""),
        "HOST": os.environ.get("DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("DB_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

AUTH_USER_MODEL = "usuarios.Usuario"

# Contraseñas: hash PBKDF2 por defecto de Django + validadores (OWASP)
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "autenticacion:home"

# Cierre de sesión automático por inactividad: 3 minutos (180 s).
# SAVE_EVERY_REQUEST renueva el plazo con cada petición del usuario.
SESSION_INACTIVITY_TIMEOUT = 180   #3minutos
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
SESSION_COOKIE_HTTPONLY = True

# La interfaz debe estar en inglés (requisito del cliente)
LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/Bogota"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"   # Nginx sirve esta carpeta en el despliegue

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Registro de errores (Documento de Arquitectura, buenas prácticas: manejo de errores y logging).
# Se escribe en la salida estándar: en el servidor Linux lo recoge systemd/journald vía Gunicorn
# (journalctl -u <servicio>). Errores 5xx y eventos de seguridad; no se registran datos de los formularios.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "ERROR", "propagate": False},
        "django.security": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
