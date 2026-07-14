"""
Configurações comuns a todos os ambientes (development, production).
Cada ambiente específico importa este módulo e sobrescreve o que for necessário.
"""
from datetime import timedelta
from pathlib import Path

import environ

from apps.core.constantes import (
    LIMITE_PAGINACAO_PADRAO,
    TAXA_THROTTLE_ANONIMO,
    TAXA_THROTTLE_LOGIN,
    TAXA_THROTTLE_USUARIO,
    TEMPO_VIDA_ACCESS_TOKEN_MIN,
    TEMPO_VIDA_REFRESH_TOKEN_DIAS,
)

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")  # lê o .env na raiz do projeto

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)  # Guard B.1 — default seguro
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",  # obrigatório para o Whitenoise (RN-09) funcionar
    "rest_framework",
    "corsheaders",
    "apps.core",
    "apps.profissionais",
    "apps.consultas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # o mais alto possível, antes do CommonMiddleware (exigência da lib)
    "whitenoise.middleware.WhiteNoiseMiddleware",  # logo após o SecurityMiddleware — ordem exigida pelo Whitenoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.MiddlewareLogAcesso",  # último — loga a resposta já finalizada (SDD-04, RN-08)
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Banco de dados — DATABASE_URL é a fonte única de verdade lida pelo Django.
# Os POSTGRES_* (ver .env.example) não são lidos pelo Django diretamente —
# eles alimentam o container `db` E são usados para montar o próprio
# DATABASE_URL no docker-compose.yml, evitando duas fontes de verdade divergentes.
DATABASES = {
    "default": env.db("DATABASE_URL"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# Arquivos estáticos (RN-09 — Whitenoise). STATIC_ROOT é obrigatório para o
# collectstatic (RN-12) ter para onde escrever — sem isso, o entrypoint falha.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# SDD-03, RN-07 — paginação global; SDD-03, RN-15 — exception handler de domínio
# SDD-04 — autenticação JWT, permissão padrão e rate limiting
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": LIMITE_PAGINACAO_PADRAO,  # mesma constante do SDD-03 — nunca hardcoded de novo
    "EXCEPTION_HANDLER": "apps.core.exception_handler.tratar_erro_global",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": TAXA_THROTTLE_ANONIMO,
        "user": TAXA_THROTTLE_USUARIO,
        "login": TAXA_THROTTLE_LOGIN,
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=TEMPO_VIDA_ACCESS_TOKEN_MIN),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=TEMPO_VIDA_REFRESH_TOKEN_DIAS),
}

# SDD-04, RN-05 — CORS restrito às origens configuradas via .env, nunca "*"
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = False  # nunca True neste projeto

# RN-08 do SDD-01 — toda saída de log vai para stdout/stderr, nunca arquivo local.
# SDD-04, RN-16 — logs em JSON estruturado de uma linha por evento.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.core.logging.FormatadorJSON"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        # Sem isso, o DEFAULT_LOGGING do Django (aplicado antes deste dict, com
        # disable_existing_loggers=False) mantém seu próprio handler de console em
        # texto puro no logger "django" quando DEBUG=True — cada requisição com erro
        # geraria uma linha extra não-JSON, violando RN-16/CA-16. Redireciona
        # explicitamente para o handler JSON e evita duplicação via propagação ao root.
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"level": "WARNING", "propagate": True},
        "urllib3": {"level": "WARNING", "propagate": True},
    },
}
