from rest_framework import status

from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "contrato_test_data.json")
CAMPOS = TEST_DATA["campos"]


class ContratoProfissionaisTestCase(APITestCaseAutenticado):
    """
    Testes de contrato (RN-07 do SDD-05).
    Protegem o formato do JSON retornado — um consumidor externo da API
    depende dessa estrutura permanecer estável.
    """

    CAMPOS_ESPERADOS_PROFISSIONAL = set(TEST_DATA["campos_esperados_profissional"])

    def test_listagem_profissionais_segue_contrato_de_paginacao_padrao(self):
        """SDD-05, CA-06."""
        resposta = self.client.get(TEST_DATA["endpoint_profissionais"])
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(resposta.data.keys()),
            {CAMPOS["count"], CAMPOS["next"], CAMPOS["previous"], CAMPOS["results"]},
        )

    def test_item_de_profissional_contem_exatamente_os_campos_do_contrato(self):
        """SDD-05, CA-06 — nem mais, nem menos campos que o serializer define."""
        Profissional.objects.create(**TEST_DATA["profissional_teste"])
        resposta = self.client.get(TEST_DATA["endpoint_profissionais"])
        item = resposta.data[CAMPOS["results"]][0]
        self.assertEqual(set(item.keys()), self.CAMPOS_ESPERADOS_PROFISSIONAL)
