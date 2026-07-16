from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework import status

from apps.consultas.models import Consulta
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "consulta_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]
DATAS = TEST_DATA["datas"]


class ConsultaRefinamentosTestCase(APITestCaseAutenticado):
    """Cobre SDD-03 (extensões), CA-17 a CA-20."""

    def setUp(self):
        super().setUp()
        self.profissional = Profissional.objects.create(
            **DADOS_COMPARTILHADOS["profissionais"]["carla_lima"]
        )

    def test_criar_consulta_com_mesmo_profissional_e_horario_retorna_400_com_conflito(self):
        """SDD-03, CA-17."""
        Consulta.objects.create(
            profissional=self.profissional,
            data_hora=DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
        )

        resposta = self.client.post(
            TEST_DATA["endpoint_consultas"],
            {
                CAMPOS["profissional"]: self.profissional.id,
                CAMPOS["data_hora"]: DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
            },
        )
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        # Mensagem em si não vem do fixture — é a própria asserção validada contra
        # ErroConflitoHorario (apps/core/exceptions.py), fonte única de verdade.
        self.assertIn("consulta marcada", str(resposta.data).lower())

    def test_criar_consulta_mesmo_horario_profissional_diferente_e_permitido(self):
        """SDD-03, CA-18 — constraint é por par profissional+horário, não por horário isolado."""
        Consulta.objects.create(
            profissional=self.profissional,
            data_hora=DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
        )
        outro_profissional = Profissional.objects.create(**TEST_DATA["outro_profissional"])

        resposta = self.client.post(
            TEST_DATA["endpoint_consultas"],
            {
                CAMPOS["profissional"]: outro_profissional.id,
                CAMPOS["data_hora"]: DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
            },
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)

    def test_listar_consultas_de_multiplos_profissionais_nao_gera_n_mais_um_queries(self):
        """SDD-03, CA-19 — confirma select_related("profissional") aplicado."""
        template = TEST_DATA["profissional_template_multiplos"]
        for indice in range(5):
            profissional = Profissional.objects.create(
                nome_social=f"Profissional {indice}",
                registro_profissional=f"CRM-{indice:04d}",
                email=f"prof{indice}@example.com",
                **template,
            )
            Consulta.objects.create(
                profissional=profissional, data_hora=f"2026-08-{indice + 1:02d}T10:00:00Z"
            )

        with CaptureQueriesContext(connection) as contexto:
            resposta = self.client.get(TEST_DATA["endpoint_consultas"])

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data[CAMPOS["results"]]), 5)
        # Sem select_related, seriam ao menos 1 query de contagem + 1 de listagem + 5 (uma por
        # profissional relacionado) = 7+. Com select_related, o número não escala com N.
        self.assertLess(len(contexto), 5)

    def test_listar_consultas_com_filtro_de_intervalo_de_data_retorna_apenas_dentro_do_intervalo(
        self,
    ):
        """SDD-03, CA-20."""
        Consulta.objects.create(profissional=self.profissional, data_hora=DATAS["fora_intervalo_1"])
        Consulta.objects.create(profissional=self.profissional, data_hora=DATAS["dentro_intervalo"])
        Consulta.objects.create(profissional=self.profissional, data_hora=DATAS["fora_intervalo_2"])

        resposta = self.client.get(
            f"{TEST_DATA['endpoint_consultas']}?data_inicio={DATAS['filtro_data_inicio']}&data_fim={DATAS['filtro_data_fim']}"
        )
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data[CAMPOS["results"]]), 1)
        self.assertTrue(
            resposta.data[CAMPOS["results"]][0][CAMPOS["data_hora"]].startswith(
                DATAS["dentro_intervalo"][:10]
            )
        )
