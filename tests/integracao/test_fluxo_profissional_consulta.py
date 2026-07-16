from rest_framework import status

from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "integracao_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
ENDPOINTS = TEST_DATA["endpoints"]
CAMPOS = TEST_DATA["campos"]
DATAS = TEST_DATA["datas"]


class FluxoProfissionalConsultaTestCase(APITestCaseAutenticado):
    """
    Testes de integração/B2B (RN-06 do SDD-05).
    Cobre o ciclo de vida completo atravessando os módulos
    Profissional e Consulta, incluindo a regra de exclusão protegida
    definida no SDD-02 (RN-04) e SDD-03 (CA-08).
    """

    def test_fluxo_completo_criar_consulta_bloquear_exclusao_liberar_exclusao(self):
        """SDD-05, CA-04."""
        # 1. Cria profissional
        resposta = self.client.post(ENDPOINTS["profissionais"], TEST_DATA["profissional_carla"])
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        id_profissional = resposta.data[CAMPOS["id"]]

        # 2. Cria consulta vinculada
        resposta = self.client.post(
            ENDPOINTS["consultas"],
            {
                CAMPOS["profissional"]: id_profissional,
                CAMPOS["data_hora"]: DADOS_COMPARTILHADOS["datas"]["consulta_tarde"],
            },
        )
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        id_consulta = resposta.data[CAMPOS["id"]]

        # 3. Tenta excluir profissional — deve ser bloqueado (integração models + serializers + view)
        resposta = self.client.delete(f"{ENDPOINTS['profissionais']}{id_profissional}/")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Exclui a consulta
        resposta = self.client.delete(f"{ENDPOINTS['consultas']}{id_consulta}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

        # 5. Agora a exclusão do profissional deve funcionar
        resposta = self.client.delete(f"{ENDPOINTS['profissionais']}{id_profissional}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

    def test_busca_consultas_por_profissional_retorna_apenas_do_profissional_correto(self):
        """Integração entre filtro de Consulta e cadastro de múltiplos Profissionais (SDD-03, CA-13)."""
        resposta_a = self.client.post(ENDPOINTS["profissionais"], TEST_DATA["profissional_a"])
        resposta_b = self.client.post(ENDPOINTS["profissionais"], TEST_DATA["profissional_b"])
        id_a = resposta_a.data[CAMPOS["id"]]
        id_b = resposta_b.data[CAMPOS["id"]]

        self.client.post(
            ENDPOINTS["consultas"],
            {
                CAMPOS["profissional"]: id_a,
                CAMPOS["data_hora"]: DADOS_COMPARTILHADOS["datas"]["consulta_manha"],
            },
        )
        self.client.post(
            ENDPOINTS["consultas"],
            {CAMPOS["profissional"]: id_b, CAMPOS["data_hora"]: DATAS["consulta_b"]},
        )

        resposta = self.client.get(f"{ENDPOINTS['consultas']}?{CAMPOS['profissional']}={id_a}")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data[CAMPOS["results"]]), 1)
        self.assertEqual(resposta.data[CAMPOS["results"]][0][CAMPOS["profissional"]], id_a)
