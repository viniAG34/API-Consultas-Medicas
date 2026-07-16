from rest_framework import status

from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "consulta_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]


class ConsultaErrosTestCase(APITestCaseAutenticado):
    """Cobre SDD-03, CA-11, CA-12."""

    def setUp(self):
        super().setUp()
        self.profissional = Profissional.objects.create(
            **DADOS_COMPARTILHADOS["profissionais"]["carla_lima"]
        )

    def test_criar_consulta_com_profissional_inexistente_retorna_400_com_mensagem(self):
        """SDD-03, CA-11."""
        resposta = self.client.post(
            TEST_DATA["endpoint_consultas"],
            {
                CAMPOS["profissional"]: TEST_DATA["profissional_inexistente"],
                CAMPOS["data_hora"]: DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
            },
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(CAMPOS["profissional"], resposta.data)

    def test_criar_consulta_sem_data_hora_retorna_400_com_campo_apontado(self):
        """SDD-03, CA-12."""
        resposta = self.client.post(
            TEST_DATA["endpoint_consultas"],
            {
                CAMPOS["profissional"]: self.profissional.id,
            },
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(CAMPOS["data_hora"], resposta.data)
