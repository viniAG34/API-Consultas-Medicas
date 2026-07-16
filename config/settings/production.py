"""Configurações específicas de produção."""

from .base import *  # noqa: F401,F403

DEBUG = False

# Hardening HTTPS/cookies — necessário atrás do ALB que o SDD-07 vai criar.
# SECURE_PROXY_SSL_HEADER confia no cabeçalho X-Forwarded-Proto do ALB para
# que o Django reconheça a requisição como HTTPS (o Gunicorn recebe HTTP puro
# do load balancer internamente).
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
