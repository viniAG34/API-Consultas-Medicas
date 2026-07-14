import logging

from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from apps.core.exceptions import ErroAplicacao

logger = logging.getLogger("lacrei.erros")


def tratar_erro_global(exc, context):
    # Exceções de domínio (ver CONVENCOES-CODIGO.md) — despacho único por tipo.
    # match/case aqui é estrutural (isinstance por padrão de classe), não um
    # substituto de if/elif comum — é o único lugar do projeto que faz essa tradução.
    match exc:
        case ErroAplicacao():
            # Uma única cláusula cobre toda a hierarquia — cada subclasse já carrega
            # seu próprio status_http, então não há status hardcoded aqui.
            logger.warning(
                exc.mensagem,
                extra={"path": _path(context), "metodo": _metodo(context), **exc.contexto},
            )
            return Response({"detail": exc.mensagem}, status=exc.status_http)
        case _:
            resposta = drf_exception_handler(exc, context)
            if resposta is not None:
                return resposta

            # Erro não tratado pelo DRF nem pela hierarquia de domínio — 500 genérico
            logger.error(
                "Erro não tratado",
                exc_info=True,
                extra={"path": _path(context), "metodo": _metodo(context)},
            )
            return Response({"detail": "Erro interno do servidor."}, status=500)


def _path(context) -> str:
    request = context.get("request")
    return getattr(request, "path", "?")


def _metodo(context) -> str:
    request = context.get("request")
    return getattr(request, "method", "?")
