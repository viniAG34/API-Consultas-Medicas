from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from apps.core.constantes import TAXA_THROTTLE_LOGIN, TAXA_THROTTLE_USUARIO
from tests.base import APITestCaseAutenticado, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "seguranca_test_data.json")
ENDPOINTS = TEST_DATA["endpoints"]
CAMPOS = TEST_DATA["campos"]
IPS = TEST_DATA["ips"]


class RateLimitingUsuarioTestCase(APITestCaseAutenticado):
    """Cobre SDD-04, CA-11, CA-13."""

    def test_usuario_dentro_do_limite_normal_nenhuma_requisicao_e_bloqueada(self):
        """SDD-04, CA-13."""
        for _ in range(10):
            resposta = self.client.get(ENDPOINTS["profissionais"])
            self.assertNotEqual(resposta.status_code, status.HTTP_429_TOO_MANY_REQUESTS)

    def test_usuario_excedendo_limite_de_requisicoes_retorna_429_com_retry_after(self):
        """SDD-04, CA-11."""
        limite = int(TAXA_THROTTLE_USUARIO.split("/")[0])  # "100/minuto" -> 100

        ultima_resposta = None
        for _ in range(limite + 1):
            ultima_resposta = self.client.get(ENDPOINTS["profissionais"])
            if ultima_resposta.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                break

        self.assertEqual(ultima_resposta.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", ultima_resposta)


class RateLimitingLoginTestCase(APITestCase):
    """
    Cobre SDD-04, CA-12. Não herda de APITestCaseAutenticado — exercita o
    endpoint de login, público por design (RN-15).
    """

    def setUp(self):
        super().setUp()
        # Mesmo racional de tests/seguranca/test_autenticacao.py: cache de
        # throttle limpo explicitamente + IP dedicado, para não herdar cota
        # de outro teste que também bate em /api/token/.
        cache.clear()
        Usuario = get_user_model()
        Usuario.objects.create_user(**TEST_DATA["usuarios"]["rate"])

    def test_tentativas_repetidas_de_login_excedendo_limite_retorna_429(self):
        """
        SDD-04, CA-12.

        Nota: o CA descreve que "o log registra o IP com nível WARNING". Na
        implementação atual, o log estruturado de acesso (MiddlewareLogAcesso,
        apps/core/middleware.py) não captura o IP como campo explícito — só
        path/metodo/status/usuario/duracao_ms. O 429 é logado automaticamente
        pelo logger nativo "django.request" do Django (nível WARNING, via
        RN-16), mas sem o IP no texto da mensagem. Este teste valida o que é
        efetivamente garantido hoje (429 + log WARNING); adicionar o IP como
        campo estruturado do log é uma mudança de escopo do SDD-04, fora
        desta sessão de testes — registrado como ponto de atenção no relatório
        desta sessão.
        """
        limite = int(TAXA_THROTTLE_LOGIN.split("/")[0])  # "5/minuto" -> 5
        payload = {
            CAMPOS["username"]: TEST_DATA["usuarios"]["rate"][CAMPOS["username"]],
            CAMPOS["password"]: TEST_DATA["senha_errada_rate"],
        }

        with self.assertLogs("django.request", level="WARNING") as captura:
            ultima_resposta = None
            for _ in range(limite + 2):
                ultima_resposta = self.client.post(
                    ENDPOINTS["token"], payload, REMOTE_ADDR=IPS["rate_login"]
                )
                if ultima_resposta.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
                    break

        self.assertEqual(ultima_resposta.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("Retry-After", ultima_resposta)
        self.assertIn("WARNING", "\n".join(captura.output))
