# SDD-01 — Setup do Projeto
> Não depende de outros SDDs — é a base de toda a implementação.
> Última atualização: 2026-07-09

---

## Responsabilidade

Estabelecer a estrutura inicial do projeto Django com Django REST Framework, gerenciamento de dependências via Poetry, e ambiente containerizado com PostgreSQL via Docker Compose, pronto para receber os modelos e endpoints das próximas fases.

**Não faz:** não define models, não define endpoints, não define autenticação. Apenas garante que `docker-compose up` sobe uma aplicação Django vazia conectada ao PostgreSQL, com dependências gerenciadas e configuração de settings pronta para os módulos seguintes.

---

## Regras de negócio

- RN-01: O gerenciamento de dependências do projeto é feito exclusivamente via Poetry (`pyproject.toml` + `poetry.lock`), sem uso de `requirements.txt` solto.
- RN-02: O ambiente de desenvolvimento e produção deve ser reproduzível via Docker — nenhuma dependência do projeto pode exigir instalação manual fora do container.
- RN-03: As configurações sensíveis (`SECRET_KEY`, credenciais do banco, `DEBUG`) nunca ficam hardcoded no `settings.py` — vêm de variáveis de ambiente (`.env`, nunca versionado).
- RN-04: O banco de dados da aplicação é PostgreSQL em todos os ambientes (dev, staging, produção) — sem SQLite, nem em desenvolvimento local, para evitar divergência de comportamento entre ambientes.
- RN-05: O container da aplicação Django e o container do PostgreSQL são serviços separados no `docker-compose.yml`, comunicando-se via rede interna do Compose.
- RN-06: A configuração do Django (`settings`) é dividida por ambiente (`base`, `development`, `production`), nunca um único arquivo com lógica condicional de ambiente embutida.
- RN-07: `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` são sempre lidos de variável de ambiente — nunca hardcoded — para permitir troca de domínio entre staging e produção sem alteração de código.
- RN-08: Toda saída de log da aplicação vai para stdout/stderr, nunca para arquivo local em disco, para compatibilidade com coleta de logs em ambiente containerizado (ex: CloudWatch Logs). **Nota:** o formato específico (JSON estruturado) é definido no SDD-04, RN-16 — aqui só se garante o destino (stdout), não o formato.
- RN-09: Arquivos estáticos são servidos via Whitenoise em produção — a aplicação não depende de servidor externo de estáticos para funcionar corretamente após deploy.
- RN-10: A imagem Docker de produção roda com usuário não-root e é construída em multi-stage build, minimizando superfície de ataque e tamanho da imagem final.
- RN-11: A aplicação expõe um endpoint de health check (`/health/`) que confirma não só que o processo está de pé, mas que a conexão com o banco de dados está funcional — necessário para load balancer/orquestrador validar a saúde do serviço na AWS.
- RN-12: `migrate` e `collectstatic` são executados como parte do entrypoint do container na subida da aplicação, nunca como passo manual esquecível.

---

## Critérios de aceite

- CA-01: Dado o repositório clonado com Docker instalado
         Quando executado `docker-compose up --build`
         Então os containers `web` (Django) e `db` (PostgreSQL) sobem sem erro e a aplicação responde na porta configurada

- CA-02: Dado o container `web` em execução
         Quando acessado o endpoint raiz ou admin do Django (`/admin/`)
         Então a página carrega sem erro 500, confirmando que a conexão com o PostgreSQL está funcional

- CA-03: Dado o arquivo `.env.example` no repositório
         Quando um novo desenvolvedor copia para `.env` e preenche as variáveis
         Então o projeto sobe sem necessidade de nenhuma outra configuração manual

- CA-04: Dado o `pyproject.toml` configurado
         Quando executado `poetry install` (fora do container, para desenvolvimento local sem Docker)
         Então todas as dependências são resolvidas e instaladas sem conflito de versões

- CA-05: Dado o `.gitignore` do projeto
         Quando o repositório é inspecionado
         Então `.env`, `__pycache__`, `*.pyc` e arquivos de ambiente virtual não aparecem versionados

- CA-06: Dado `DJANGO_SETTINGS_MODULE=config.settings.production`
         Quando a aplicação é iniciada
         Então ela carrega as configurações de produção (DEBUG=False, hosts restritos) sem depender de nenhum arquivo de settings único condicional

- CA-07: Dado o container em execução
         Quando acessado o endpoint `GET /health/`
         Então retorna `200` com confirmação de conexão ativa ao PostgreSQL, e retorna erro (não 200) se o banco estiver inacessível

- CA-08: Dado o container de produção construído
         Quando inspecionado o processo em execução dentro do container
         Então ele roda sob usuário não-root (não `root` nem UID 0)

- CA-09: Dado o container subindo pela primeira vez em um ambiente novo
         Quando o entrypoint é executado
         Então `migrate` e `collectstatic` rodam automaticamente antes da aplicação começar a aceitar requisições

- CA-10: Dado o Django rodando em modo produção
         Quando qualquer log é emitido pela aplicação
         Então ele aparece em stdout/stderr do container (verificável via `docker logs`), nunca em arquivo dentro do container

- CA-11: Dado o `.env` preenchido apenas com `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_PORT`
         Quando executado `docker-compose up`
         Então o container `web` conecta ao banco com sucesso, sem o desenvolvedor precisar montar `DATABASE_URL` manualmente

---

## Erros e exceções

- Guard A.1 (crítico — propaga): variável de ambiente obrigatória ausente (`SECRET_KEY`, `DATABASE_URL`) → aplicação falha ao subir com erro claro no log, nunca com fallback silencioso para valor inseguro
- Guard A.2 (crítico — propaga): falha de conexão com o banco no health check → endpoint retorna erro explícito (não 200), permitindo que o load balancer da AWS marque a instância como não saudável
- Guard B.1 (fallback): `DEBUG` não definido no `.env` → assume `False` por padrão (fail-safe para produção)
- Guard B.2 (fallback): `collectstatic` falha por diretório ausente → entrypoint cria o diretório automaticamente antes de tentar novamente, sem derrubar o container
- Guard C (silencioso): variáveis opcionais de configuração (ex: `ALLOWED_HOSTS` extra) ausentes → usa valor default documentado, sem interromper o boot

---

## Referência de implementação

**Estrutura de diretórios esperada ao final deste SDD:**
```
lacrei-desafio/
├── pyproject.toml
├── poetry.lock
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── config/              ← projeto Django (settings, urls, wsgi/asgi)
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py      ← comum a todos os ambientes
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── apps/                ← apps Django ficam aqui (profissionais, consultas — próximos SDDs)
│   └── core/             ← app leve para health check e utilitários transversais
├── docker-entrypoint.sh ← roda migrate + collectstatic antes de subir o servidor
└── manage.py
```

**Dependências mínimas esperadas no `pyproject.toml`:**
- `django`, `djangorestframework`, `psycopg2-binary` (ou `psycopg[binary]`), **`django-environ`** (variáveis de ambiente — decisão fechada: o SDD-04 usa a sintaxe `env.list(...)` desta biblioteca especificamente), `gunicorn` (para produção), `whitenoise` (para arquivos estáticos em produção)

**`settings/base.py` — setup do `django-environ` (usado por todos os settings seguintes, incluindo SDD-04):**
```python
import environ

env = environ.Env()
environ.Env.read_env()  # lê o .env na raiz do projeto

SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)  # Guard B.1 — default seguro
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",  # obrigatório para o Whitenoise (RN-09) funcionar
    "rest_framework",
    "apps.core",
    "apps.profissionais",
    "apps.consultas",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # logo após o SecurityMiddleware — ordem exigida pelo Whitenoise
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # "apps.core.middleware.MiddlewareLogAcesso" entra aqui no SDD-04 — ver RN-16/RN-17 de lá
]

# Arquivos estáticos (RN-09 — Whitenoise). STATIC_ROOT é obrigatório para o
# collectstatic (RN-12) ter para onde escrever — sem isso, o entrypoint falha.
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Banco de dados — DATABASE_URL é a fonte única de verdade lida pelo Django.
# Os POSTGRES_* (ver .env.example) não são lidos pelo Django diretamente —
# eles alimentam o container `db` (imagem oficial do Postgres) E são usados
# para montar o próprio DATABASE_URL no docker-compose.yml (ver abaixo).
# Isso evita duas fontes de verdade divergentes para a mesma credencial.
DATABASES = {
    "default": env.db("DATABASE_URL"),
}
```

> **Nota:** `BASE_DIR` é definido pelo `startproject` padrão do Django (topo do
> `settings/base.py`, via `Path(__file__).resolve().parent.parent.parent`) — omitido acima
> por já ser convenção conhecida, mas precisa existir antes da linha `STATIC_ROOT`.
> `MIDDLEWARE` fica incompleto de propósito nesta fase — `MiddlewareLogAcesso` só existe a
> partir do SDD-04, que mostra a lista final com ele incluído.

**`docker-compose.yml` — serviços mínimos (concreto, resolvendo a relação `DATABASE_URL` ↔ `POSTGRES_*`):**
```yaml
services:
  web:
    build: .
    depends_on:
      - db
    ports:
      - "8000:8000"
    env_file: .env
    environment:
      # Montado a partir dos mesmos POSTGRES_* do .env — nunca hardcoded,
      # nunca digitado duas vezes. "db" é o nome do serviço na rede do Compose.
      DATABASE_URL: postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:${POSTGRES_PORT}/${POSTGRES_DB}

  db:
    image: postgres:16
    restart: always
    environment:
      POSTGRES_DB: ${POSTGRES_DB}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

> **Por que isso importa:** sem essa montagem explícita, `DATABASE_URL` e os `POSTGRES_*`
> viram duas fontes de verdade que podem divergir silenciosamente (ex: alguém troca a senha
> em um lugar e esquece do outro, e a aplicação simplesmente não conecta). Aqui, `POSTGRES_*`
> é a única coisa que o desenvolvedor edita no `.env` — o Compose monta `DATABASE_URL`
> automaticamente a partir deles antes de passar para o container `web`.

**Dockerfile — pontos de atenção para produção:**
- Multi-stage build (estágio de build separado do estágio final de runtime, reduzindo tamanho da imagem)
- Criação de usuário não-root (`USER appuser`) antes do `CMD`/`ENTRYPOINT`
- `docker-entrypoint.sh` como `ENTRYPOINT`, responsável por `python manage.py migrate` e `python manage.py collectstatic --noinput` antes de iniciar o Gunicorn

**Endpoint de health check (`apps/core`):**
- `GET /health/` — verifica conexão ativa com o PostgreSQL (ex: `SELECT 1`) e retorna `200 {"status": "ok"}` ou `503` em caso de falha

**`apps/core/views.py`:**
```python
from django.db import connection
from rest_framework.views import APIView
from rest_framework.response import Response


class VerificarSaude(APIView):
    """
    GET /health/ — usado pelo Docker healthcheck (SDD-01) e pelo load
    balancer da AWS (SDD-07). Neste SDD-01, ainda não existe IsAuthenticated
    global, então esta view funciona sem restrição nenhuma. A partir do
    SDD-04 (RN-15), quando a autenticação global for aplicada, este mesmo
    arquivo precisa ganhar `permission_classes = [AllowAny]` — ver nota lá.
    """

    def get(self, request):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception:
            return Response({"status": "erro"}, status=503)
        return Response({"status": "ok"})
```

**`apps/core/urls.py`:**
```python
from django.urls import path
from .views import VerificarSaude

urlpatterns = [
    path("health/", VerificarSaude.as_view(), name="health"),
]
```

- **Atenção (cross-referência SDD-04):** quando a autenticação global (`IsAuthenticated`) for implementada no SDD-04, esta view precisa declarar `permission_classes = [AllowAny]` explicitamente — health check não pode exigir token, pois load balancer e Docker healthcheck (SDD-07) não enviam `Authorization`. Neste SDD-01 (antes do SDD-04 existir) isso ainda não é um problema, mas fica registrado aqui para não ser esquecido. **O código concreto dessa alteração está no SDD-04, seção de referência de implementação — junto com `TokenObtainPairViewPublica` e as views do Swagger, que recebem o mesmo tratamento.**

> **Nota sobre CA-04 (uso local sem Docker):** fora do Compose, não há interpolação automática
> — o desenvolvedor que rodar `poetry run python manage.py runserver` direto (sem Docker)
> precisa preencher `DATABASE_URL` manualmente no `.env` apontando para `localhost` em vez de
> `db` (ex: `postgres://usuario:senha@localhost:5432/lacrei`), já que "db" só existe como
> hostname dentro da rede do Compose.

---

## Checklist de implementação

- [ ] Nomenclatura em português para apps e módulos que vierem a seguir (este SDD é infraestrutura, então nomes técnicos em inglês aqui são aceitáveis — ex: `config`, `apps`)
- [ ] Zero credenciais hardcoded — tudo via `.env`
- [ ] `docker-compose up --build` sobe sem erro
- [ ] `.env.example` documentado com todas as variáveis necessárias
- [ ] `.gitignore` cobre `.env`, cache Python e artefatos do Poetry
- [ ] README (mesmo que provisório neste ponto) já documenta como subir o ambiente local
- [ ] Settings divididos em `base`/`development`/`production`, selecionados via `DJANGO_SETTINGS_MODULE`
- [ ] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` parametrizados via `.env`
- [ ] Logging configurado para stdout/stderr, sem arquivo local
- [ ] Whitenoise configurado para servir estáticos em produção
- [ ] Dockerfile multi-stage com usuário não-root
- [ ] Endpoint `/health/` implementado e validando conexão com o banco
- [ ] `INSTALLED_APPS` inclui `django.contrib.staticfiles`, `rest_framework` e os três apps do projeto
- [ ] `MIDDLEWARE` inclui `WhiteNoiseMiddleware` logo após `SecurityMiddleware` (ordem exigida)
- [ ] `STATIC_ROOT`, `STATIC_URL` e `STATICFILES_STORAGE` configurados — sem isso, `collectstatic` (RN-12) falha
- [ ] `docker-entrypoint.sh` executa `migrate` e `collectstatic` automaticamente no boot
- [ ] `DATABASE_URL` é a única variável lida por `DATABASES` no settings — nunca os `POSTGRES_*` diretamente pelo Django
- [ ] `docker-compose.yml` monta `DATABASE_URL` do serviço `web` a partir dos mesmos `POSTGRES_*` do `.env` (sem duplicar a credencial em dois lugares)
- [ ] Chaves do `docker-compose.yml` conferidas em minúsculo (`ports`, `environment`, `volumes`) — YAML é case-sensitive, `Ports` (maiúsculo) não é um erro de sintaxe, é uma chave nova ignorada silenciosamente pelo Compose (bug menor real, encontrado durante o provisionamento manual da EC2 no SDD-07)
