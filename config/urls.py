from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.consultas.views import ConsultaViewSet
from apps.core.throttling import ThrottleLogin
from apps.profissionais.views import ProfissionalViewSet

router = DefaultRouter()
router.register(r"profissionais", ProfissionalViewSet, basename="profissional")
router.register(r"consultas", ConsultaViewSet, basename="consulta")


class TokenObtainPairViewPublica(TokenObtainPairView):
    """Pública por design (SDD-04, RN-15) — exigir autenticação aqui impediria qualquer login."""

    permission_classes = [AllowAny]
    throttle_classes = [ThrottleLogin]


class TokenRefreshViewPublica(TokenRefreshView):
    """Pública por design (SDD-04, RN-15) — mesmo motivo do endpoint de obtenção de token."""

    permission_classes = [AllowAny]


class SpectacularAPIViewPublica(SpectacularAPIView):
    """Pública por design (SDD-04, RN-15) — documentação deve ser navegável sem token."""

    permission_classes = [AllowAny]


class SpectacularSwaggerViewPublica(SpectacularSwaggerView):
    """Pública por design (SDD-04, RN-15) — mesmo motivo da view de schema acima."""

    permission_classes = [AllowAny]


class SpectacularRedocViewPublica(SpectacularRedocView):
    """Pública por design (SDD-04, RN-15) — mesmo motivo da view de schema acima."""

    permission_classes = [AllowAny]


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.core.urls")),
    path("api/token/", TokenObtainPairViewPublica.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshViewPublica.as_view(), name="token_refresh"),
    path("api/schema/", SpectacularAPIViewPublica.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerViewPublica.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocViewPublica.as_view(url_name="schema"), name="redoc"),
    path("api/", include(router.urls)),
]
