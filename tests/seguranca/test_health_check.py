from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from tests.base import carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "seguranca_test_data.json")
ENDPOINTS = TEST_DATA["endpoints"]
CAMPOS = TEST_DATA["campos"]
IPS = TEST_DATA["ips"]

# Exceção deliberada à RN-11 do SDD-05: testa endpoints públicos por design
# (SDD-04, RN-15) — não herda de APITestCaseAutenticado.


class HealthCheckPublicoTestCase(APITestCase):
    """Cobre SDD-04, CA-14, CA-15."""

    def setUp(self):
        super().setUp()
        cache.clear()

    def test_health_check_sem_authorization_retorna_200(self):
        """SDD-04, CA-14."""
        resposta = self.client.get(ENDPOINTS["health"])
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data[CAMPOS["status"]], "ok")

    def test_obter_token_sem_autenticacao_previa_retorna_200(self):
        """SDD-04, CA-15 — confirma que o próprio endpoint de login não exige login prévio (RN-15)."""
        Usuario = get_user_model()
        Usuario.objects.create_user(**TEST_DATA["usuarios"]["health"])

        resposta = self.client.post(
            ENDPOINTS["token"],
            TEST_DATA["usuarios"]["health"],
            REMOTE_ADDR=IPS["health"],
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn(CAMPOS["access"], resposta.data)
