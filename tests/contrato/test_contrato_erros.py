from rest_framework import status

from apps.consultas.models import Consulta
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "contrato_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]


class ContratoErrosTestCase(APITestCaseAutenticado):
    """
    Testes de contrato (RN-07 do SDD-05).
    Protegem o formato de erro retornado pela API — um consumidor externo
    precisa sempre saber onde procurar a mensagem, seja erro de validação
    padrão do DRF, seja exceção de domínio do projeto.
    """

    def test_erro_de_validacao_de_campo_segue_formato_padrao_do_drf(self):
        """SDD-05, CA-07 — {"campo": ["mensagem"]}, nunca string genérica."""
        payload_sem_nome_social = {
            chave: valor
            for chave, valor in DADOS_COMPARTILHADOS["profissionais"]["ana_souza"].items()
            if chave != CAMPOS["nome_social"]
        }
        resposta = self.client.post(TEST_DATA["endpoint_profissionais"], payload_sem_nome_social)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(CAMPOS["nome_social"], resposta.data)
        self.assertIsInstance(resposta.data[CAMPOS["nome_social"]], list)

    def test_erro_de_excecao_de_dominio_segue_formato_detail(self):
        """SDD-05, CA-07 — exceções de domínio (ErroAplicacao) sempre respondem {"detail": "..."}."""
        profissional = Profissional.objects.create(
            **DADOS_COMPARTILHADOS["profissionais"]["ana_souza"]
        )
        Consulta.objects.create(
            profissional=profissional, data_hora=DADOS_COMPARTILHADOS["datas"]["consulta_manha"]
        )

        resposta = self.client.delete(f"{TEST_DATA['endpoint_profissionais']}{profissional.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(resposta.data.keys()), {CAMPOS["detail"]})
        self.assertIsInstance(resposta.data[CAMPOS["detail"]], str)
