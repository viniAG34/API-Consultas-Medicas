from rest_framework import status

from apps.consultas.models import Consulta
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "profissional_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]


class ProfissionalErrosTestCase(APITestCaseAutenticado):
    """Cobre SDD-03, CA-02, CA-03, CA-08."""

    def setUp(self):
        super().setUp()
        self.payload_valido = DADOS_COMPARTILHADOS["profissionais"]["ana_souza"]

    def test_criar_profissional_sem_contato_retorna_400_com_mensagem_especifica(self):
        """
        SDD-03, CA-02. RN-03 é regra de negócio (email ou telefone obrigatório) —
        levantada como ErroValidacao (domínio), traduzida por tratar_erro_global no
        formato {"detail": "..."}, mesmo tratamento dado ao conflito de horário em
        ConsultaSerializer (correção de pente-fino de 2026-07-15).
        """
        payload = {
            chave: valor for chave, valor in self.payload_valido.items() if chave != CAMPOS["email"]
        }
        resposta = self.client.post(TEST_DATA["endpoint_profissionais"], payload)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(set(resposta.data.keys()), {CAMPOS["detail"]})
        # Mensagem em si não vem do fixture — é a própria asserção validada contra
        # ErroValidacao (apps/core/exceptions.py), fonte única de verdade.
        self.assertIn("email ou telefone", resposta.data[CAMPOS["detail"]])

    def test_criar_profissional_sem_nome_social_retorna_400_com_campo_apontado(self):
        """SDD-03, CA-03."""
        payload = {
            chave: valor
            for chave, valor in self.payload_valido.items()
            if chave != CAMPOS["nome_social"]
        }
        resposta = self.client.post(TEST_DATA["endpoint_profissionais"], payload)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn(CAMPOS["nome_social"], resposta.data)

    def test_excluir_profissional_com_consulta_vinculada_retorna_400_com_mensagem_explicita(self):
        """SDD-03, CA-08 — verifica status E mensagem, não apenas 'não é 200'."""
        profissional = Profissional.objects.create(**self.payload_valido)
        Consulta.objects.create(
            profissional=profissional, data_hora=DADOS_COMPARTILHADOS["datas"]["consulta_manha"]
        )

        resposta = self.client.delete(f"{TEST_DATA['endpoint_profissionais']}{profissional.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        # Mensagem de erro em si não vem do fixture: é a própria asserção sendo
        # validada contra apps/core/exceptions.py (ErroRecursoProtegido) — extraí-la
        # para o JSON criaria uma segunda fonte de verdade fora de sincronia possível.
        self.assertIn("vinculadas", str(resposta.data).lower())
        self.assertTrue(Profissional.objects.filter(id=profissional.id).exists())
