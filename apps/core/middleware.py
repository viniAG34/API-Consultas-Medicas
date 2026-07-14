import logging
import time

logger = logging.getLogger("lacrei.acesso")


class MiddlewareLogAcesso:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        inicio = time.monotonic()
        resposta = self.get_response(request)
        duracao_ms = round((time.monotonic() - inicio) * 1000, 1)

        usuario = getattr(request, "user", None)
        identificador_usuario = usuario.username if usuario and usuario.is_authenticated else "anonimo"

        logger.info(
            "Requisição processada",
            extra={
                "path": request.path,
                "metodo": request.method,
                "status": resposta.status_code,
                "usuario": identificador_usuario,
                "duracao_ms": duracao_ms,
            },
        )
        return resposta
