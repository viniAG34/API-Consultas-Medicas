import json
from functools import lru_cache
from pathlib import Path

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


@lru_cache(maxsize=None)
def _ler_json_cacheado(caminho: str) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def carregar_dados_teste(arquivo_teste: str, nome_arquivo: str) -> dict:
    """
    Carrega um arquivo de fixture JSON da pasta fixtures/ ao lado do arquivo de
    teste chamador. Usado para tirar magic strings (payloads, endpoints, nomes
    de campo) do corpo dos testes — passe sempre `__file__` do módulo chamador.

    Cacheado por caminho resolvido (lru_cache): vários arquivos de teste do
    mesmo módulo que compartilham a mesma fixture (ex: os 3 arquivos de
    tests/consultas/ lendo consulta_test_data.json) leem o JSON do disco uma
    única vez por sessão de teste, não uma vez por arquivo — o dict retornado
    é compartilhado entre eles. Isso só é seguro porque nenhum teste faz
    mutação in-place em TEST_DATA (sempre `{**TEST_DATA["x"], ...}`, nunca
    `TEST_DATA["x"][...] = ...`); se algum teste futuro precisar mutar,
    copie o dict antes (`dict(TEST_DATA["x"])`) em vez de alterar o cache
    compartilhado.
    """
    caminho = Path(arquivo_teste).with_name("fixtures").joinpath(nome_arquivo).resolve()
    return _ler_json_cacheado(str(caminho))


def carregar_dados_compartilhados(nome_arquivo: str = "dados_compartilhados.json") -> dict:
    """
    Carrega uma fixture JSON compartilhada entre mais de um módulo de teste,
    de tests/fixtures/ (nível raiz de tests/, ao lado deste arquivo). Use para
    payloads/valores idênticos reaproveitados por mais de uma pasta (ex: o
    mesmo profissional usado em tests/consultas/ e tests/regressao/) — dados
    específicos de um único módulo continuam em fixtures/<modulo>_test_data.json.
    """
    return carregar_dados_teste(__file__, nome_arquivo)


class APITestCaseAutenticado(APITestCase):
    """
    Base para qualquer teste que exercite endpoint protegido pelo
    IsAuthenticated global (SDD-04, RN-02). Cria um usuário e autentica
    o client automaticamente em setUp() via force_authenticate — evita
    testar o fluxo de token em todo teste de CRUD (isso já é coberto
    isoladamente em tests/seguranca/test_autenticacao.py).
    """

    def setUp(self):
        super().setUp()
        Usuario = get_user_model()
        self.usuario_teste = Usuario.objects.create_user(
            username="usuario_teste",
            password="senha-teste-nao-usar-em-producao",
        )
        self.client.force_authenticate(user=self.usuario_teste)
