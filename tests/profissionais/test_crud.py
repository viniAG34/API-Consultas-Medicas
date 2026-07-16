from rest_framework import status

from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "profissional_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]


class ProfissionalCRUDTestCase(APITestCaseAutenticado):
    """Cobre SDD-03, CA-01, CA-04, CA-05, CA-06, CA-07, CA-09."""

    def setUp(self):
        super().setUp()
        self.payload_valido = DADOS_COMPARTILHADOS["profissionais"]["ana_souza"]

    def test_criar_profissional_com_payload_valido_retorna_201(self):
        """SDD-03, CA-01."""
        resposta = self.client.post(TEST_DATA["endpoint_profissionais"], self.payload_valido)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIn(CAMPOS["id"], resposta.data)
        self.assertIn(CAMPOS["criado_em"], resposta.data)
        self.assertIn(CAMPOS["atualizado_em"], resposta.data)

    def test_detalhar_profissional_existente_retorna_200_com_dados_completos(self):
        """SDD-03, CA-04."""
        profissional = Profissional.objects.create(**self.payload_valido)
        resposta = self.client.get(f"{TEST_DATA['endpoint_profissionais']}{profissional.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(
            resposta.data[CAMPOS["nome_social"]], self.payload_valido[CAMPOS["nome_social"]]
        )
        self.assertEqual(
            resposta.data[CAMPOS["registro_profissional"]],
            self.payload_valido[CAMPOS["registro_profissional"]],
        )

    def test_detalhar_profissional_inexistente_retorna_404(self):
        """SDD-03, CA-05."""
        resposta = self.client.get(
            f"{TEST_DATA['endpoint_profissionais']}{TEST_DATA['id_inexistente']}/"
        )
        self.assertEqual(resposta.status_code, status.HTTP_404_NOT_FOUND)

    def test_atualizar_profissional_existente_retorna_200_com_atualizado_em_alterado(self):
        """SDD-03, CA-06."""
        profissional = Profissional.objects.create(**self.payload_valido)
        atualizado_em_original = profissional.atualizado_em

        payload_atualizado = {
            **self.payload_valido,
            CAMPOS["nome_social"]: TEST_DATA["nome_social_atualizado"],
        }
        resposta = self.client.put(
            f"{TEST_DATA['endpoint_profissionais']}{profissional.id}/", payload_atualizado
        )

        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta.data[CAMPOS["nome_social"]], TEST_DATA["nome_social_atualizado"])
        profissional.refresh_from_db()
        self.assertGreater(profissional.atualizado_em, atualizado_em_original)

    def test_excluir_profissional_sem_consultas_retorna_204(self):
        """SDD-03, CA-07."""
        profissional = Profissional.objects.create(**self.payload_valido)
        resposta = self.client.delete(f"{TEST_DATA['endpoint_profissionais']}{profissional.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Profissional.objects.filter(id=profissional.id).exists())

    def test_listar_profissionais_retorna_200_com_lista_paginada(self):
        """SDD-03, CA-09."""
        Profissional.objects.create(**self.payload_valido)
        Profissional.objects.create(
            **{**self.payload_valido, **TEST_DATA["outro_profissional_override"]}
        )

        resposta = self.client.get(TEST_DATA["endpoint_profissionais"])
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(resposta.data.keys()),
            {CAMPOS["count"], CAMPOS["next"], CAMPOS["previous"], CAMPOS["results"]},
        )
        self.assertEqual(resposta.data[CAMPOS["count"]], 2)
