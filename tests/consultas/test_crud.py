from rest_framework import status

from apps.consultas.models import Consulta
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "consulta_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]
DATAS = TEST_DATA["datas"]


class ConsultaCRUDTestCase(APITestCaseAutenticado):
    """Cobre SDD-03, CA-10, CA-13, CA-14, CA-15."""

    def setUp(self):
        super().setUp()
        self.profissional = Profissional.objects.create(
            **DADOS_COMPARTILHADOS["profissionais"]["carla_lima"]
        )

    def test_criar_consulta_com_payload_valido_retorna_201(self):
        """SDD-03, CA-10."""
        resposta = self.client.post(
            TEST_DATA["endpoint_consultas"],
            {
                CAMPOS["profissional"]: self.profissional.id,
                CAMPOS["data_hora"]: DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
            },
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIn(CAMPOS["id"], resposta.data)
        self.assertEqual(resposta.data[CAMPOS["profissional"]], self.profissional.id)

    def test_listar_consultas_filtradas_por_profissional_retorna_apenas_do_profissional(self):
        """SDD-03, CA-13."""
        outro_profissional = Profissional.objects.create(**TEST_DATA["outro_profissional"])
        Consulta.objects.create(
            profissional=self.profissional,
            data_hora=DADOS_COMPARTILHADOS["datas"]["consulta_manha"],
        )
        Consulta.objects.create(profissional=outro_profissional, data_hora=DATAS["consulta_3"])

        resposta = self.client.get(
            f"{TEST_DATA['endpoint_consultas']}?{CAMPOS['profissional']}={self.profissional.id}"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data[CAMPOS["results"]]), 1)
        self.assertEqual(
            resposta.data[CAMPOS["results"]][0][CAMPOS["profissional"]], self.profissional.id
        )

    def test_listar_consultas_de_profissional_sem_consulta_retorna_200_com_lista_vazia(self):
        """SDD-03, CA-14."""
        resposta = self.client.get(
            f"{TEST_DATA['endpoint_consultas']}?{CAMPOS['profissional']}={self.profissional.id}"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data[CAMPOS["results"]], [])

    def test_excluir_consulta_existente_retorna_204(self):
        """SDD-03, CA-15 — exclusão de consulta não é protegida, diferente de profissional."""
        consulta = Consulta.objects.create(
            profissional=self.profissional,
            data_hora=DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
        )
        resposta = self.client.delete(f"{TEST_DATA['endpoint_consultas']}{consulta.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Consulta.objects.filter(id=consulta.id).exists())
