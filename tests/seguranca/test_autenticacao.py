import datetime

from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from tests.base import carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "seguranca_test_data.json")
ENDPOINTS = TEST_DATA["endpoints"]
CAMPOS = TEST_DATA["campos"]
IPS = TEST_DATA["ips"]

# Exceção deliberada à RN-11 do SDD-05: este arquivo testa o comportamento
# SEM autenticação (e a própria obtenção de token) — não herda de
# APITestCaseAutenticado, que já viria autenticado por force_authenticate.


class AutenticacaoTestCase(APITestCase):
    """Cobre SDD-04, CA-01, CA-03, CA-04, CA-05."""

    def setUp(self):
        super().setUp()
        # Limpa o cache de throttle explicitamente: ThrottleLogin (AnonRateThrottle)
        # é resolvido por IP, e o cache padrão do Django (LocMemCache) não é
        # automaticamente esvaziado entre métodos de um TestCase — sem isso, testes
        # que fazem múltiplas chamadas a /api/token/ poderiam esbarrar na cota de
        # 5/minuto deixada por um teste anterior (TAXA_THROTTLE_LOGIN, SDD-04 RN-13).
        cache.clear()
        Usuario = get_user_model()
        self.usuario = Usuario.objects.create_user(**TEST_DATA["usuarios"]["auth"])

    def test_login_com_credenciais_validas_retorna_200_com_tokens(self):
        """SDD-04, CA-01."""
        resposta = self.client.post(
            ENDPOINTS["token"],
            TEST_DATA["usuarios"]["auth"],
            REMOTE_ADDR=IPS["login"],
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn(CAMPOS["access"], resposta.data)
        self.assertIn(CAMPOS["refresh"], resposta.data)

    def test_rota_protegida_sem_header_authorization_retorna_401(self):
        """SDD-04, CA-03."""
        resposta = self.client.get(ENDPOINTS["profissionais"])
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_access_token_expirado_retorna_401_com_mensagem_de_expiracao(self):
        """SDD-04, CA-04."""
        token = AccessToken.for_user(self.usuario)
        token.set_exp(lifetime=datetime.timedelta(seconds=-1))  # já expirado

        resposta = self.client.get(
            ENDPOINTS["profissionais"],
            HTTP_AUTHORIZATION=f"Bearer {token}",
        )
        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("expir", str(resposta.data).lower())

    def test_refresh_token_valido_retorna_200_com_novo_access_token(self):
        """SDD-04, CA-05."""
        refresh = RefreshToken.for_user(self.usuario)

        resposta = self.client.post(
            ENDPOINTS["token_refresh"],
            {CAMPOS["refresh"]: str(refresh)},
            REMOTE_ADDR=IPS["refresh"],
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertIn(CAMPOS["access"], resposta.data)


class AutenticacaoSenhaInvalidaTestCase(APITestCase):
    """
    Cobre SDD-04, CA-02, isolado de qualquer outro teste de rate limiting
    (lacuna deixada na Fase 4: a verificação manual anterior esbarrou no
    throttle de login compartilhado com outro teste). Usa um IP dedicado
    (REMOTE_ADDR) e limpa o cache de throttle em setUp() para garantir que
    a cota de TAXA_THROTTLE_LOGIN (5/minuto) esteja sempre zerada aqui,
    independente da ordem de execução dos demais testes da suíte.
    """

    def setUp(self):
        super().setUp()
        cache.clear()
        Usuario = get_user_model()
        self.usuario = Usuario.objects.create_user(**TEST_DATA["usuarios"]["ca02"])

    def test_login_com_senha_invalida_retorna_401_e_loga_warning_sem_vazar_senha(self):
        """SDD-04, CA-02 — verifica 401 e que a tentativa falha é registrada com
        WARNING (via logger django.request, mapeado ao formatter JSON — SDD-04,
        RN-16), sem que a senha em texto apareça no log."""
        senha_incorreta = TEST_DATA["senha_invalida_ca02"]

        with self.assertLogs("django.request", level="WARNING") as captura:
            resposta = self.client.post(
                ENDPOINTS["token"],
                {
                    CAMPOS["username"]: TEST_DATA["usuarios"]["ca02"][CAMPOS["username"]],
                    CAMPOS["password"]: senha_incorreta,
                },
                REMOTE_ADDR=IPS["ca02"],
            )

        self.assertEqual(resposta.status_code, status.HTTP_401_UNAUTHORIZED)

        log_completo = "\n".join(captura.output)
        self.assertIn("WARNING", log_completo)
        self.assertNotIn(senha_incorreta, log_completo)
