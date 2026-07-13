# SDD-04 — Segurança e Autenticação
> Leia SDD-01, SDD-02 e SDD-03 antes de implementar.
> Última atualização: 2026-07-09

---

## Responsabilidade

Definir e implementar autenticação da API, restrição de CORS, proteção contra SQL Injection (reforço sobre o que o ORM já garante), sanitização/validação de entrada, e logging estruturado de acesso e erros.

**Não faz:** não define os endpoints de negócio em si (SDD-03), não define testes formais (SDD-05). Define exclusivamente a camada de segurança que envolve os endpoints já existentes.

---

## Regras de negócio

- RN-01: Toda rota de escrita (`POST`, `PUT`, `PATCH`, `DELETE`) exige autenticação válida — requisição sem token retorna `401`.
- RN-02: Rotas de leitura (`GET`) também exigem autenticação — o desafio não distingue rota pública de privada, e dados de profissionais/consultas de saúde não devem ficar expostos sem autenticação.
- RN-03: A autenticação é feita via **JWT** (`djangorestframework-simplejwt`), com endpoint de obtenção de token (`/api/token/`) e renovação (`/api/token/refresh/`).
- RN-04: O `SECRET_KEY` do Django e a chave de assinatura do JWT nunca têm valor default — ausência da variável de ambiente impede o boot da aplicação (Guard A do SDD-01, RN-03).
- RN-05: CORS é restrito às origens explicitamente configuradas via `CORS_ALLOWED_ORIGINS` no `.env` — nunca `*`, mesmo em desenvolvimento.
- RN-06: Toda entrada de usuário passa pela validação do serializer (SDD-03) antes de tocar o banco — nenhuma view aceita `request.data` bruto sem passar por serializer.
- RN-07: A proteção contra SQL Injection é estrutural: 100% das queries passam pelo Django ORM. Nenhuma query SQL raw é permitida neste projeto (reforça RN do SDD-01/CLAUDE.md).
- RN-08: Toda requisição autenticada é logada (método, path, usuário, status code, tempo de resposta) — log de acesso.
- RN-09: Todo erro não tratado (500) é logado com stack trace no servidor, mas a resposta ao cliente nunca expõe o stack trace ou detalhes internos.
- RN-10: Tentativas de autenticação falha (senha/token inválido) são logadas com nível `WARNING`, sem registrar a senha em texto, apenas o identificador da tentativa (usuário, IP, timestamp).
- RN-11: Tokens JWT têm tempo de expiração curto para o access token (ex: 60 minutos) e um refresh token de vida mais longa (ex: 7 dias), ambos parametrizados via constante, nunca número mágico solto no código.
- RN-12: A API aplica rate limiting por usuário autenticado e por IP para requisições anônimas (ex: tentativas de login), prevenindo abuso, brute force e negação de serviço básica.
- RN-13: O endpoint de obtenção de token (`/api/token/`) tem um limite de tentativas mais restritivo que os demais endpoints, por ser alvo natural de ataques de força bruta.
- RN-14: Excedido o limite de requisições, a API retorna `429 Too Many Requests` com header indicando o tempo de espera, nunca um erro genérico.
- RN-15: **Exceções obrigatórias ao `IsAuthenticated` global** — os seguintes endpoints são explicitamente públicos (`permission_classes = [AllowAny]`), pois exigir autenticação neles quebra o próprio funcionamento do sistema: `POST /api/token/` e `POST /api/token/refresh/` (sem eles, ninguém consegue obter o primeiro token — loop impossível), `GET /health/` (SDD-01 — load balancer e Docker healthcheck do SDD-07 não enviam JWT), e `/api/schema/`, `/api/docs/`, `/api/redoc/` (SDD-08 — precisam ser navegáveis por quem ainda não tem token). Nenhum outro endpoint tem essa exceção.
- RN-16: Logs de acesso e de erro são emitidos em **JSON estruturado de uma linha por evento** (não texto livre), com campos padrão (`ts`, `nivel`, `modulo`, `mensagem`) e contexto extra quando relevante (`usuario`, `path`, `status`, `duracao_ms`) — permite filtragem e busca eficiente em produção via `docker logs` ou coletor de observabilidade, reforçando RN-08 do SDD-01 (stdout).
- RN-17: O `tratar_erro_global` é o **único ponto** de tradução entre exceções de domínio (`apps/core/exceptions.py` — hierarquia definida em `CONVENCOES-CODIGO.md`) e resposta HTTP, usando `match/case` sobre o tipo da exceção. Nenhuma view ou serializer decide status HTTP por conta própria para esses casos (ver SDD-03, RN-15).

---

## Critérios de aceite

- CA-01: Dado um usuário/senha válidos cadastrados
         Quando enviado `POST /api/token/` com as credenciais
         Então retorna `200` com `access` e `refresh` tokens válidos

- CA-02: Dado um usuário/senha inválidos
         Quando enviado `POST /api/token/`
         Então retorna `401` e o log registra a tentativa falha com nível `WARNING`, sem registrar a senha

- CA-03: Dado qualquer rota de `Profissional` ou `Consulta`
         Quando a requisição é enviada sem header `Authorization`
         Então retorna `401`

- CA-04: Dado um `access token` expirado
         Quando usado em qualquer requisição autenticada
         Então retorna `401` com mensagem indicando token expirado

- CA-05: Dado um `refresh token` válido
         Quando enviado `POST /api/token/refresh/`
         Então retorna `200` com um novo `access token`

- CA-06: Dado o `CORS_ALLOWED_ORIGINS` configurado com um domínio específico
         Quando uma requisição chega de uma origem diferente da configurada
         Então o navegador bloqueia a resposta (header CORS ausente/negado para a origem não permitida)

- CA-07: Dado um erro não tratado ocorrendo no servidor (500)
         Quando a resposta é enviada ao cliente
         Então o corpo da resposta não contém stack trace, nome de arquivo interno ou detalhes de implementação — apenas uma mensagem genérica

- CA-08: Dado esse mesmo erro 500
         Quando inspecionados os logs do servidor
         Então o stack trace completo está registrado, junto com o path e método da requisição que originou o erro

- CA-09: Dado qualquer requisição autenticada bem-sucedida
         Quando processada
         Então um log de acesso é registrado contendo método, path, status code e identificador do usuário autenticado

- CA-10: Dado o `SECRET_KEY` ausente na variável de ambiente
         Quando a aplicação tenta subir
         Então o boot falha imediatamente com erro claro, nunca com um valor default silencioso

- CA-11: Dado um usuário autenticado excedendo o limite de requisições configurado (`LIMITE_REQUISICOES_USUARIO_HORA`)
         Quando uma nova requisição é enviada dentro da mesma janela de tempo
         Então retorna `429` com header `Retry-After` indicando quando tentar novamente

- CA-12: Dado tentativas repetidas de `POST /api/token/` com credenciais inválidas a partir do mesmo IP
         Quando o limite de tentativas de login (`LIMITE_TENTATIVAS_LOGIN_IP`) é excedido
         Então retorna `429`, e o log registra o IP com nível `WARNING`

- CA-13: Dado um usuário dentro do limite normal de uso
         Quando realiza requisições dentro da janela de tempo permitida
         Então nenhuma delas é bloqueada por rate limiting

- CA-14: Dado `GET /health/`, `GET /api/schema/`, `GET /api/docs/` ou `GET /api/redoc/`
         Quando acessados sem header `Authorization`
         Então retornam normalmente (200), sem exigir token — exceções explícitas de RN-15

- CA-15: Dado `POST /api/token/` sem nenhuma autenticação prévia
         Quando enviado com credenciais válidas
         Então retorna `200` com os tokens, confirmando que o próprio endpoint de login não exige login prévio (RN-15)

- CA-16: Dado qualquer log de acesso ou erro emitido pela aplicação
         Quando inspecionado via `docker logs`
         Então cada linha é um JSON válido contendo ao menos `ts`, `nivel`, `modulo` e `mensagem`

- CA-17: Dado qualquer exceção de domínio levantada (`ErroConflitoHorario`, `ErroRecursoProtegido`, etc.)
         Quando ela chega ao `tratar_erro_global`
         Então é traduzida para o status HTTP correspondente (`status_http` da própria exceção) via `match/case`, sem precisar de tratamento adicional na view

---

## Erros e exceções

- Guard A (crítico — propaga): `SECRET_KEY` ou chave JWT ausente no ambiente → aplicação não sobe, erro explícito no log de boot
- Guard B.1 (fallback): falha ao registrar log de acesso (ex: problema de I/O do handler de log) → requisição continua normalmente, apenas o log daquela requisição específica é perdido, sem derrubar a API
- Guard B.2 (fallback): backend de cache do throttling indisponível (ex: se usar Redis futuramente e ele cair) → `AnonRateThrottle`/`UserRateThrottle` do DRF falha de forma aberta por padrão; aceitável nesta fase pois o desafio não exige alta disponibilidade de cache — documentar como limitação conhecida
- Guard C (silencioso): tentativa de autenticação com token malformado (não apenas expirado, mas inválido/corrompido) → tratado pelo próprio middleware do `simplejwt`, retorna 401 padrão sem necessidade de log verboso adicional

---

## Referência de implementação

**Dependência adicional no `pyproject.toml`:**
- `djangorestframework-simplejwt`

**`settings/base.py` — configuração de autenticação e CORS:**
```python
from datetime import timedelta
from apps.core.constantes import (
    LIMITE_PAGINACAO_PADRAO,       # já definida no SDD-03
    TEMPO_VIDA_ACCESS_TOKEN_MIN,
    TEMPO_VIDA_REFRESH_TOKEN_DIAS,
    TAXA_THROTTLE_ANONIMO,
    TAXA_THROTTLE_USUARIO,
    TAXA_THROTTLE_LOGIN,
)

# Nota: este dicionário estende o REST_FRAMEWORK já iniciado no SDD-03 (paginação).
# Não é uma segunda atribuição — é o mesmo dicionário, mostrado aqui completo para
# refletir o estado após este SDD-04.
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": LIMITE_PAGINACAO_PADRAO,  # mesma constante do SDD-03 — nunca hardcoded de novo
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": TAXA_THROTTLE_ANONIMO,
        "user": TAXA_THROTTLE_USUARIO,
        "login": TAXA_THROTTLE_LOGIN,
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=TEMPO_VIDA_ACCESS_TOKEN_MIN),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=TEMPO_VIDA_REFRESH_TOKEN_DIAS),
}

CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])
CORS_ALLOW_ALL_ORIGINS = False  # nunca True neste projeto
```

**`apps/core/constantes.py` (adição deste SDD):**
```python
# SDD-04 — Segurança e Autenticação
TEMPO_VIDA_ACCESS_TOKEN_MIN = 60      # SDD-04, RN-11
TEMPO_VIDA_REFRESH_TOKEN_DIAS = 7     # SDD-04, RN-11
TAXA_THROTTLE_ANONIMO = "20/minuto"   # SDD-04, RN-12
TAXA_THROTTLE_USUARIO = "100/minuto"  # SDD-04, RN-12
TAXA_THROTTLE_LOGIN = "5/minuto"      # SDD-04, RN-13
```

**`apps/core/throttling.py` — throttle dedicado ao endpoint de login (RN-13):**
```python
from rest_framework.throttling import AnonRateThrottle


class ThrottleLogin(AnonRateThrottle):
    scope = "login"
```

**`config/urls.py` — aplicando o throttle dedicado e tornando as rotas de token públicas (RN-15):**
```python
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from apps.core.throttling import ThrottleLogin


class TokenObtainPairViewPublica(TokenObtainPairView):
    """Pública por design (RN-15) — exigir autenticação aqui impediria qualquer login."""
    permission_classes = [AllowAny]
    throttle_classes = [ThrottleLogin]


class TokenRefreshViewPublica(TokenRefreshView):
    """Pública por design (RN-15) — mesmo motivo do endpoint de obtenção de token."""
    permission_classes = [AllowAny]


urlpatterns += [
    path("api/token/", TokenObtainPairViewPublica.as_view(), name="token_obtain_pair"),
    path("api/token/refresh/", TokenRefreshViewPublica.as_view(), name="token_refresh"),
]
```

**`apps/core/views.py` — aplicando `AllowAny` à view de health check já criada no SDD-01 (RN-15):**
```python
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class VerificarSaude(APIView):
    """Pública por design (RN-15) — ver SDD-01 para a versão original desta view."""
    permission_classes = [AllowAny]

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response({"status": "erro"}, status=503)
        return Response({"status": "ok"})
```

**`apps/core/logging.py` — formatter JSON estruturado (RN-16), inspirado no padrão validado no projeto do bot de agendamento:**
```python
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
    Instanciado diretamente pelo LOGGING (dictConfig) em settings/base.py —
    ver abaixo. Este arquivo não expõe função de setup: o dictConfig do
    Django já cuida de toda a integração, sem precisar de uma chamada manual
    equivalente ao `configurar_logging()` usado no projeto do bot (que não
    tinha o mecanismo nativo de dictConfig do Django).
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
```

**`settings/base.py` — integração via `LOGGING` (dictConfig), preferido sobre chamar `configurar_logging` direto, por ser o padrão idiomático do Django:**
```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {"()": "apps.core.logging.FormatadorJSON"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "json"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django.db.backends": {"level": "WARNING", "propagate": True},
        "urllib3": {"level": "WARNING", "propagate": True},
    },
}
```

**`apps/core/exception_handler.py` — despacho central via `match/case` (RN-17):**
```python
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
            return Response(
                {"detail": "Erro interno do servidor."},
                status=500,
            )


def _path(context) -> str:
    request = context.get("request")
    return getattr(request, "path", "?")


def _metodo(context) -> str:
    request = context.get("request")
    return getattr(request, "method", "?")
```

Referenciado em `settings/base.py`:
```python
REST_FRAMEWORK["EXCEPTION_HANDLER"] = "apps.core.exception_handler.tratar_erro_global"
```

**`apps/core/middleware.py` — log de acesso (RN-08):**
```python
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
```

**`settings/base.py` — `MIDDLEWARE` final, estendendo a lista base do SDD-01:**
```python
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.core.middleware.MiddlewareLogAcesso",  # último — loga a resposta já finalizada
]
```

**Nota sobre RN-02 (leitura também exige autenticação):** essa é uma decisão mais restritiva do que estritamente exigido pelo PDF do desafio (que pede apenas "controle básico de autenticação"), mas justificável para dados de saúde — vale mencionar explicitamente no README (SDD-09) como justificativa técnica de segurança, mostrando raciocínio além do mínimo pedido.

---

## Checklist de implementação

- [ ] `djangorestframework-simplejwt` instalado e configurado como autenticação padrão
- [ ] `IsAuthenticated` como permissão padrão global (nenhuma rota de negócio pública)
- [ ] `TEMPO_VIDA_ACCESS_TOKEN_MIN` e `TEMPO_VIDA_REFRESH_TOKEN_DIAS` como constantes, não números soltos
- [ ] `TAXA_THROTTLE_ANONIMO`, `TAXA_THROTTLE_USUARIO` e `TAXA_THROTTLE_LOGIN` configuradas como constantes
- [ ] `ThrottleLogin` aplicado especificamente ao endpoint `/api/token/`, mais restritivo que os demais
- [ ] `TokenObtainPairViewPublica` e `TokenRefreshViewPublica` com `permission_classes = [AllowAny]` explícito (RN-15) — sem isso, ninguém consegue logar
- [ ] View de `/health/` (SDD-01) com `permission_classes = [AllowAny]` explícito — código concreto em `apps/core/views.py` (`VerificarSaude`), não apenas nota conceitual
- [ ] `MIDDLEWARE` final inclui `apps.core.middleware.MiddlewareLogAcesso` como último item da lista
- [ ] Views do `drf-spectacular` (SDD-08) com acesso público explícito, se o SDD-08 for implementado
- [ ] `apps/core/logging.py` com `FormatadorJSON` configurado via `LOGGING` (dictConfig) em `settings/base.py`
- [ ] `apps/core/exceptions.py` criado com a hierarquia `ErroAplicacao` e subclasses (ver `CONVENCOES-CODIGO.md`)
- [ ] `tratar_erro_global` usa `match/case` sobre `ErroAplicacao` como único ponto de tradução para status HTTP — nenhuma view decide isso por conta própria
- [ ] `MiddlewareLogAcesso` e `tratar_erro_global` usam `extra={}` para contexto — nunca embutem dados na string da mensagem
- [ ] Loggers verbosos (`django.db.backends`, `urllib3`) silenciados para `WARNING`
- [ ] `CORS_ALLOW_ALL_ORIGINS` nunca `True`; origens vêm de `.env`
- [ ] `tratar_erro_global` configurado como `EXCEPTION_HANDLER` do DRF
- [ ] `MiddlewareLogAcesso` registrado em `MIDDLEWARE` no settings
- [ ] Logs configurados para stdout/stderr (RN-08 do SDD-01), nunca arquivo local
- [ ] Nenhuma senha ou token em texto aparece em log, em nenhuma circunstância
- [ ] Todos os critérios de aceite cobertos por testes (formalizado no SDD-05)
