import logging

from django.db import connection
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger("lacrei.saude")


class VerificarSaude(APIView):
    """
    GET /health/ — usado pelo Docker healthcheck (SDD-01) e pelo load
    balancer da AWS (SDD-07). Pública por design (SDD-04, RN-15): load
    balancer e Docker healthcheck não enviam Authorization.
    """

    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            logger.error("Health check falhou: conexão com banco indisponível", exc_info=True)
            return Response({"status": "erro"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": "ok"})
