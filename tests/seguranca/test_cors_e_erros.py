from unittest.mock import patch

from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from tests.base import APITestCaseAutenticado, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "seguranca_test_data.json")
ENDPOINTS = TEST_DATA["endpoints"]
CORS = TEST_DATA["cors"]

# Cobertura extra desta sessão (Fase 5), não prevista literalmente no SDD-05
# original: CORS (SDD-04, CA-06) e erro 500 genuíno (SDD-04, CA-07/CA-08),
# ambos identificados como lacuna a fechar explicitamente nesta rodada.

HEADER_CORS = "Access-Control-Allow-Origin"


@override_settings(CORS_ALLOWED_ORIGINS=[CORS["origem_permitida"]])
class CorsTestCase(APITestCase):
    """
    Cobre SDD-04, CA-06. Usa /health/ (público, AllowAny) para isolar o
    comportamento de CORS de qualquer questão de autenticação — o
    CorsMiddleware atua na resposta independentemente da rota exigir JWT.
    """

    def test_requisicao_com_origem_permitida_recebe_header_cors(self):
        resposta = self.client.get(ENDPOINTS["health"], HTTP_ORIGIN=CORS["origem_permitida"])
        self.assertEqual(resposta.get(HEADER_CORS), CORS["origem_permitida"])

    def test_requisicao_com_origem_nao_permitida_nao_recebe_header_cors(self):
        resposta = self.client.get(ENDPOINTS["health"], HTTP_ORIGIN=CORS["origem_nao_permitida"])
        self.assertNotIn(HEADER_CORS, resposta)


class Erro500GenuinoTestCase(APITestCaseAutenticado):
    """Cobre SDD-04, CA-07 (resposta ao cliente não vaza detalhe interno) e CA-08
    (log do servidor contém o stack trace completo)."""

    def test_excecao_nao_mapeada_retorna_500_generico_e_loga_stack_trace_completo(self):
        mensagem_erro_interno = TEST_DATA["mensagem_erro_interno_simulada"]

        # Nota de implementação: mockar QuerySet.count diretamente não funciona aqui —
        # o Paginator do Django (django/core/paginator.py) verifica via inspect se
        # `count` é um método "sem argumentos" antes de chamá-lo, e um Mock falha
        # nessa checagem silenciosamente, fazendo o Paginator cair no fallback
        # `len(self.object_list)` sem nunca invocar o mock. Mockar o próprio
        # paginate_queryset simula de forma confiável uma falha ocorrendo durante
        # o processamento da requisição (equivalente a um erro de banco genuíno).
        with patch(
            "rest_framework.pagination.PageNumberPagination.paginate_queryset",
            side_effect=Exception(mensagem_erro_interno),
        ):
            with self.assertLogs("lacrei.erros", level="ERROR") as captura:
                resposta = self.client.get(ENDPOINTS["profissionais"])

        # CA-07 — resposta ao cliente é genérica, sem stack trace nem nome de arquivo interno
        self.assertEqual(resposta.status_code, status.HTTP_500_INTERNAL_SERVER_ERROR)
        self.assertEqual(resposta.data, {"detail": "Erro interno do servidor."})
        corpo_resposta = str(resposta.data)
        self.assertNotIn("Traceback", corpo_resposta)
        self.assertNotIn(".py", corpo_resposta)
        self.assertNotIn(mensagem_erro_interno, corpo_resposta)

        # CA-08 — log do servidor contém o stack trace completo
        log_completo = "\n".join(captura.output)
        self.assertIn("Traceback", log_completo)
        self.assertIn(mensagem_erro_interno, log_completo)
