import json
import logging
from datetime import datetime, timezone

# Campos padrão de qualquer LogRecord — usados para descobrir, por diferença,
# quais atributos foram adicionados via logger.info(..., extra={...}).
_CAMPOS_PADRAO_LOGRECORD = frozenset(
    logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
) | {"message"}


class FormatadorJSON(logging.Formatter):
    """
    Formata logs como JSON de uma linha. Campos padrão: ts, nivel, modulo,
    mensagem, + QUALQUER campo extra passado via logger.info(..., extra={...}).

    Importante: não usa uma lista fixa de nomes de campo. O `contexto` de
    ErroAplicacao (CONVENCOES-CODIGO.md, seção 4) é um "dict livre" — cada
    subclasse de exceção carrega chaves diferentes (profissional_id/data_hora
    em ErroConflitoHorario, por exemplo). Uma lista fixa descartaria
    silenciosamente qualquer chave não prevista; comparar contra os atributos
    padrão do LogRecord captura automaticamente qualquer extra, presente ou
    futuro, sem precisar atualizar este arquivo a cada nova exceção.
    """

    MAPA_NIVEIS = {
        logging.DEBUG: "DEBUG",
        logging.INFO: "INFO",
        logging.WARNING: "AVISO",
        logging.ERROR: "ERRO",
        logging.CRITICAL: "CRITICO",
    }

    def format(self, record: logging.LogRecord) -> str:
        entrada = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "nivel": self.MAPA_NIVEIS.get(record.levelno, record.levelname),
            "modulo": record.name,
            "mensagem": record.getMessage(),
        }

        for campo, valor in record.__dict__.items():
            if campo not in _CAMPOS_PADRAO_LOGRECORD:
                entrada[campo] = valor

        if record.exc_info:
            entrada["stack"] = self.formatException(record.exc_info)

        return json.dumps(entrada, ensure_ascii=False, default=str)
