from django.db import connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView


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
            return Response({"status": "erro"}, status=503)
        return Response({"status": "ok"})
