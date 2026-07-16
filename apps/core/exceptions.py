from rest_framework import status


class ErroAplicacao(Exception):
    """
    Base de toda exceção de domínio da aplicação. Nunca instanciada diretamente —
    sempre uma subclasse específica. Composição, não herança múltipla: cada subclasse
    carrega os dados relevantes ao próprio erro via __init__, não via atributos soltos
    setados depois.
    """

    status_http: int = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, mensagem: str, **contexto):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.contexto = contexto  # dict livre — usado no log estruturado (SDD-04)


class ErroValidacao(ErroAplicacao):
    """Entrada inválida que não corresponde a uma regra de negócio específica — 400."""

    status_http = status.HTTP_400_BAD_REQUEST


class ErroRegraNegocio(ErroAplicacao):
    """Violação de uma regra de negócio explícita (RN de algum SDD) — 400."""

    status_http = status.HTTP_400_BAD_REQUEST


class ErroConflitoHorario(ErroRegraNegocio):
    """Duas consultas no mesmo horário para o mesmo profissional (SDD-03, RN-11) — 400."""

    def __init__(self, profissional_id: str, data_hora):
        super().__init__(
            f"Profissional já possui consulta marcada em {data_hora}.",
            profissional_id=profissional_id,
            data_hora=str(data_hora),
        )


class ErroRecursoProtegido(ErroAplicacao):
    """
    Exclusão bloqueada por integridade referencial (ex: Profissional com Consultas —
    SDD-02, RN-04). Composição: envolve o ProtectedError original do Django como causa,
    em vez de recriar a informação.
    """

    status_http = status.HTTP_400_BAD_REQUEST

    def __init__(self, mensagem: str, causa_original: Exception | None = None):
        super().__init__(mensagem)
        self.__cause__ = causa_original


class ErroRecursoNaoEncontrado(ErroAplicacao):
    """
    Recurso referenciado não existe — 404.

    Reservada para um cenário futuro de busca por campo que não seja a PK
    (ex: um endpoint de busca de Profissional por registro_profissional).
    Hoje, RN-05 do SDD-03 resolve FK inexistente (ex: profissional_id inválido
    em Consulta) via 400 automático do PrimaryKeyRelatedField do DRF — não via
    esta exceção — e o 404 de detalhe por PK (GET /profissionais/{id}/) já é
    tratado nativamente pelo get_object() do DRF. Não remover: existe para o
    dia em que um lookup por campo não-PK precisar de um 404 de domínio
    explícito, com log estruturado via tratar_erro_global.
    """

    status_http = status.HTTP_404_NOT_FOUND
