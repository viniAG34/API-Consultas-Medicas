import logging

from django.test import TestCase
from rest_framework import status

from apps.consultas.models import Consulta
from apps.core.logging import FormatadorJSON
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado, carregar_dados_compartilhados, carregar_dados_teste

TEST_DATA = carregar_dados_teste(__file__, "regressao_test_data.json")
DADOS_COMPARTILHADOS = carregar_dados_compartilhados()
CAMPOS = TEST_DATA["campos"]


class RegressaoConflitoHorarioNaoUsaValidatorGenericoDrfTestCase(APITestCaseAutenticado):
    """
    Testes de regressão (RN-05 do SDD-05) — bug real encontrado e corrigido na Fase 3.

    Causa raiz: o `ModelSerializer` do DRF inspeciona a `UniqueConstraint` do
    model `Consulta` (`profissional` + `data_hora`) e gera automaticamente um
    `UniqueTogetherValidator`. Esse validador roda ANTES do `validate()`
    customizado de `ConsultaSerializer` — intercepta o conflito de horário
    primeiro e levanta `rest_framework.exceptions.ValidationError` diretamente,
    nunca chegando a instanciar `ErroConflitoHorario`. Isso viola SDD-03 RN-15
    (erro de regra de negócio deve ser exceção de domínio, traduzida
    centralmente por `tratar_erro_global`, nunca `ValidationError` solta).

    Comportamento incorreto observado: `POST /api/consultas/` com conflito de
    horário retornava `400` no formato `{"non_field_errors": ["The fields
    profissional, data_hora must make a unique set."]}` — mensagem genérica
    do DRF, sem passar por `tratar_erro_global` nem pela hierarquia
    `ErroAplicacao`.

    Comportamento correto garantido por este teste: com `validators = []` no
    `Meta` de `ConsultaSerializer` (`apps/consultas/serializers.py`), o
    `validate()` customizado roda e levanta `ErroConflitoHorario`, que
    `tratar_erro_global` traduz para `{"detail": "<mensagem de domínio>"}` —
    nunca `non_field_errors`. Se `validators = []` for removido no futuro,
    este teste falha (a resposta voltaria a ter `non_field_errors`).
    """

    def setUp(self):
        super().setUp()
        self.profissional = Profissional.objects.create(
            **DADOS_COMPARTILHADOS["profissionais"]["carla_lima"]
        )

    def test_criar_consulta_com_conflito_de_horario_retorna_erro_de_dominio_nao_generico_do_drf(
        self,
    ):
        data_hora_conflito = DADOS_COMPARTILHADOS["datas"]["consulta_tarde"]
        Consulta.objects.create(profissional=self.profissional, data_hora=data_hora_conflito)

        resposta = self.client.post(
            TEST_DATA["endpoint_consultas"],
            {
                CAMPOS["profissional"]: self.profissional.id,
                CAMPOS["data_hora"]: data_hora_conflito,
            },
        )

        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        # Assinatura do bug: se o UniqueTogetherValidator automático disparasse,
        # a resposta teria "non_field_errors" em vez de "detail".
        self.assertNotIn(CAMPOS["non_field_errors"], resposta.data)
        self.assertIn(CAMPOS["detail"], resposta.data)
        # Mensagem em si não vem do fixture — é a própria asserção validada contra
        # ErroConflitoHorario (apps/core/exceptions.py), fonte única de verdade.
        self.assertIn("já possui consulta marcada", resposta.data[CAMPOS["detail"]])


class RegressaoLoggerDjangoNaoDuplicaLinhaEmTextoPlanoTestCase(TestCase):
    """
    Testes de regressão (RN-05 do SDD-05) — bug real encontrado e corrigido na Fase 4.

    Causa raiz: o `DEFAULT_LOGGING` nativo do Django (`django/utils/log.py`)
    anexa ao logger `"django"` um `StreamHandler` em texto puro (ativo quando
    `DEBUG=True`) mais um handler de e-mail, com `propagate=True` (padrão do
    `logging.Logger`). Como o dictConfig deste projeto usa
    `disable_existing_loggers=False`, se `settings/base.py` (`LOGGING`) não
    sobrescrevesse explicitamente o logger `"django"`, esse handler nativo em
    texto puro permaneceria ativo — e o record ainda propagaria até o root
    logger (que tem o handler JSON do projeto), gerando DUAS linhas de log
    por evento: uma em texto puro (do Django) e outra em JSON (do root).

    Comportamento incorreto observado: toda requisição com erro (ex: `401`,
    `404`) gerava uma linha de log extra em texto puro no stdout, fora do
    padrão JSON — achado real via `docker logs` durante a Fase 4, não
    previsto originalmente no SDD-04. Isso viola RN-16 do SDD-04 (logs em
    JSON estruturado de uma linha por evento).

    Comportamento correto garantido por este teste: o logger `"django"` está
    configurado explicitamente em `settings/base.py` (`LOGGING`) com o
    `FormatadorJSON` do projeto e `propagate=False` — nenhum handler em texto
    puro anexado, e nenhuma duplicação por propagação ao root.
    """

    def test_logger_django_tem_propagate_desligado_e_usa_apenas_formatador_json(self):
        logger_django = logging.getLogger("django")

        self.assertFalse(
            logger_django.propagate,
            "logger 'django' deve ter propagate=False — do contrário o record "
            "duplicaria ao propagar para o root logger (bug original, SDD-04).",
        )
        self.assertTrue(
            logger_django.handlers,
            "logger 'django' precisa ter ao menos um handler configurado explicitamente.",
        )
        for handler in logger_django.handlers:
            self.assertIsInstance(
                handler.formatter,
                FormatadorJSON,
                "todo handler do logger 'django' deve usar o FormatadorJSON — um "
                "handler em texto puro aqui reintroduziria a linha duplicada.",
            )
