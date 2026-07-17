# API de Gerenciamento de Consultas Médicas — Lacrei Saúde

[![CI/CD](https://github.com/viniAG34/API-Consultas-Medicas/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/viniAG34/API-Consultas-Medicas/actions/workflows/ci-cd.yml)

- **Produção:** https://api-lacrei.vinisolucoes.com
- **Staging:** https://staging.api-lacrei.vinisolucoes.com
- **Documentação interativa (Swagger):** https://api-lacrei.vinisolucoes.com/api/docs/
- **Repositório:** https://github.com/viniAG34/API-Consultas-Medicas

---

## Sobre o projeto

Este projeto é a resposta ao desafio técnico de voluntariado da **Lacrei Saúde**, organização
que amplia o acesso à saúde inclusiva para a comunidade LGBTQIAPN+. A entrega é uma **API
RESTful de Gerenciamento de Consultas Médicas** — CRUD de profissionais da saúde e das
consultas vinculadas a eles — desenvolvida com qualidade de produção: segurança, testes
automatizados, CI/CD e deploy funcional em AWS, não apenas um protótipo local.

O projeto foi construído com metodologia **Spec-Driven Development (SDD)**, com apoio do
Claude Code na implementação — toda funcionalidade tem uma especificação (Regra de Negócio →
Critério de Aceite → Teste) escrita antes do código. Ver a seção
[Metodologia de desenvolvimento](#metodologia-de-desenvolvimento) para detalhes.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Framework web | Django 5 + Django REST Framework |
| Gerenciador de dependências | Poetry |
| Banco de dados | PostgreSQL 16 (todos os ambientes — sem SQLite) |
| Autenticação | JWT (`djangorestframework-simplejwt`) |
| Documentação interativa | `drf-spectacular` (Swagger UI + Redoc) |
| Estáticos em produção | Whitenoise |
| Servidor de aplicação | Gunicorn |
| Containerização | Docker + Docker Compose (multi-stage build, usuário não-root) |
| CI/CD | GitHub Actions (lint → testes → build → deploy staging → deploy produção) |
| Deploy | AWS EC2 + ECR + Nginx (reverse proxy) + Certbot (HTTPS) |
| Lint / formatação | `ruff` + `black` |

---

## Setup local (sem Docker)

Requer Python 3.12+ e [Poetry](https://python-poetry.org/) instalados na máquina.

```bash
poetry install
```

Preencha um `.env` na raiz (veja [Variáveis de ambiente](#variáveis-de-ambiente)) com
`DATABASE_URL` apontando para um PostgreSQL acessível localmente — fora do Docker Compose não
há a interpolação automática que monta `DATABASE_URL` a partir dos `POSTGRES_*`, então essa
variável precisa ser preenchida manualmente:

```env
DATABASE_URL=postgres://usuario:senha@localhost:5432/lacrei
```

Com o banco acessível, aplique as migrations e suba o servidor:

```bash
poetry run python manage.py migrate
poetry run python manage.py runserver
```

A API sobe em `http://localhost:8000/`.

---

## Setup com Docker

Requer Docker e Docker Compose. É a forma recomendada — sobe a aplicação e o PostgreSQL juntos,
com `DATABASE_URL` montada automaticamente a partir do `.env`.

```bash
docker compose up -d --build
```

O `docker-entrypoint.sh` roda `migrate` e `collectstatic` automaticamente antes de subir o
Gunicorn — não é necessário nenhum passo manual adicional. Verifique que subiu corretamente:

```bash
curl http://localhost:8000/health/
# {"status":"ok"}
```

Outros comandos úteis:

```bash
docker compose logs web --tail 30       # ver logs de boot
docker compose exec web python manage.py createsuperuser
docker compose down                     # encerrar
```

---

## Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

| Variável | Descrição |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.development` local, `config.settings.production` em staging/produção |
| `SECRET_KEY` | Chave secreta do Django — sem valor default, obrigatória (aplicação não sobe sem ela) |
| `DEBUG` | `True` em desenvolvimento, `False` em produção |
| `ALLOWED_HOSTS` | Lista separada por vírgula. **Nota importante (achado do deploy real, SDD-07):** em ambientes rodando via Docker precisa incluir também `localhost,127.0.0.1` além do domínio real — o healthcheck do `docker-compose.yml` faz a requisição de dentro do próprio container com cabeçalho `Host: localhost`, e sem essa entrada o Django rejeita com `400 DisallowedHost` antes mesmo de chegar à view |
| `CSRF_TRUSTED_ORIGINS` | Origens confiáveis para proteção CSRF |
| `DATABASE_URL` | Única variável lida por `DATABASES` no Django. Fora do Docker Compose precisa ser preenchida manualmente (`localhost`); dentro do Compose é montada automaticamente a partir dos `POSTGRES_*` |
| `POSTGRES_DB` / `POSTGRES_USER` / `POSTGRES_PASSWORD` | Credenciais do container PostgreSQL |
| `POSTGRES_HOST` | `db` (nome do serviço na rede do Compose) |
| `POSTGRES_PORT` | `5432` |
| `CORS_ALLOWED_ORIGINS` | Lista separada por vírgula das origens permitidas — nunca `*` |

Em staging/produção (na instância EC2, não no `.env` local) existem ainda as credenciais de
deploy (`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`/`AWS_REGION`, `ECR_REGISTRY`, `EC2_HOST`,
`EC2_USER`, `EC2_SSH_KEY`), que vivem em **GitHub Secrets**, nunca versionadas.

---

## Endpoints

Documentação interativa completa (gerada automaticamente via introspecção do DRF, sempre
sincronizada com o código real):

- **Swagger UI:** [`/api/docs/`](https://api-lacrei.vinisolucoes.com/api/docs/)
- **Redoc:** [`/api/redoc/`](https://api-lacrei.vinisolucoes.com/api/redoc/)
- **Schema OpenAPI (JSON/YAML):** [`/api/schema/`](https://api-lacrei.vinisolucoes.com/api/schema/)

O schema em `/api/schema/` pode ser importado diretamente em ferramentas externas — por
exemplo, o Postman aceita esse link como fonte para gerar uma coleção completa automaticamente
(collection ↔ schema ↔ código sempre em sincronia, sem manutenção manual de coleção). Isso foi
validado manualmente contra produção durante o desenvolvimento.

Principais rotas:

| Rota | Métodos | Autenticação |
|---|---|---|
| `/api/token/` | `POST` | Pública |
| `/api/token/refresh/` | `POST` | Pública |
| `/api/profissionais/` | `GET`, `POST` | JWT obrigatório |
| `/api/profissionais/{id}/` | `GET`, `PUT`, `PATCH`, `DELETE` | JWT obrigatório |
| `/api/consultas/` | `GET`, `POST` (aceita `?profissional=`, `?data_inicio=`, `?data_fim=`) | JWT obrigatório |
| `/api/consultas/{id}/` | `GET`, `PUT`, `PATCH`, `DELETE` | JWT obrigatório |
| `/health/` | `GET` | Pública |
| `/api/schema/`, `/api/docs/`, `/api/redoc/` | `GET` | Pública |

---

## Autenticação

A API usa JWT. Obtenha um token com um usuário já cadastrado:

```bash
curl -X POST https://api-lacrei.vinisolucoes.com/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "<seu-usuario>", "password": "<sua-senha>"}'
```

Resposta esperada (`200`) com `access` e `refresh`. Comando validado nesta sessão contra
produção — com credenciais inválidas a API responde exatamente como esperado:

```json
{"detail": "No active account found with the given credentials"}
```

com status `401`, confirmando o formato de erro e que o endpoint está público (não exige token
prévio — sem essa exceção ninguém conseguiria obter o primeiro token).

Use o `access` token nas rotas protegidas:

```bash
curl -H "Authorization: Bearer <access-token>" https://api-lacrei.vinisolucoes.com/api/profissionais/
```

Sem o header `Authorization`, qualquer rota de `Profissional`/`Consulta` retorna `401` —
inclusive `GET`, decisão detalhada em [Decisões técnicas](#decisões-técnicas). O token de
acesso expira em 60 minutos; use `/api/token/refresh/` com o `refresh` token (validade de 7
dias) para renovar sem logar novamente. O próprio Swagger UI (`/api/docs/`) permite autenticar
via botão "Authorize" e testar chamadas reais direto pela interface.

---

## Segurança

Mapeamento direto contra os itens de segurança exigidos pelo desafio:

| Requisito | Implementação |
|---|---|
| **Sanitização e validação dos dados** | Toda entrada passa por serializers do DRF antes de tocar o banco — nenhuma view aceita `request.data` bruto |
| **Proteção contra SQL Injection** | 100% das queries via Django ORM — zero SQL raw/concatenação em todo o projeto |
| **CORS configurado corretamente** | `CORS_ALLOWED_ORIGINS` restrito às origens explícitas via `.env` — `CORS_ALLOW_ALL_ORIGINS` nunca `True` |
| **Autenticação** | JWT obrigatório em toda rota de negócio, inclusive `GET` (decisão além do mínimo pedido — ver [Decisões técnicas](#decisões-técnicas)) |
| **Logs de acesso e erros** | JSON estruturado (`ts`, `nivel`, `modulo`, `mensagem` + contexto), nunca texto livre — stack trace completo no servidor, nunca exposto ao cliente |
| **Rate limiting** (além do pedido no desafio) | Throttle dedicado no login (5/min, vs. 20/min padrão anônimo) — `/api/token/` é alvo natural de força bruta |

---

## Executando os testes

Suíte completa, via container efêmero com `tests/` montado por bind mount (a imagem de
produção não inclui `tests/` — ver `.dockerignore`):

```bash
docker compose run --rm -v "$(pwd)/tests:/app/tests" web python manage.py test
```

No PowerShell, o equivalente é `-v ${PWD}/tests:/app/tests`. Todos os comandos abaixo foram
executados nesta sessão contra o container real — 40 testes no total, 0 falhas:

```bash
# CRUD (profissionais + consultas) — 19 testes
docker compose run --rm -v "$(pwd)/tests:/app/tests" web python manage.py test tests.profissionais tests.consultas

# Integração (fluxo completo profissional → consulta) — 2 testes
docker compose run --rm -v "$(pwd)/tests:/app/tests" web python manage.py test tests.integracao

# Regressão (bugs reais já corrigidos) — 2 testes
docker compose run --rm -v "$(pwd)/tests:/app/tests" web python manage.py test tests.regressao

# Contrato (formato estável do JSON de resposta) — 4 testes
docker compose run --rm -v "$(pwd)/tests:/app/tests" web python manage.py test tests.contrato

# Segurança (autenticação, rate limiting, CORS, health check) — parte dos 19 acima ficam em tests.seguranca
docker compose run --rm -v "$(pwd)/tests:/app/tests" web python manage.py test tests.seguranca
```

Se estiver rodando localmente sem Docker (Poetry, banco acessível em `localhost`):

```bash
poetry run python manage.py test
```

**Nota (Git Bash no Windows):** se o bind mount vier vazio (`Found 0 test(s)`), prefixe o
comando com `MSYS_NO_PATHCONV=1` — o Git Bash reescreve caminhos POSIX passados a binários
não-MSYS como o `docker`, quebrando o mount silenciosamente. Não afeta PowerShell nem
Linux/Mac.

---

## CI/CD

Pipeline via GitHub Actions ([`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml)),
com 5 jobs em sequência estrita (`needs`) — nenhuma etapa avança se a anterior falhar, e nenhum
job usa `continue-on-error`:

1. **`lint`** — `ruff check .` + `black --check .`
2. **`testes`** — sobe um PostgreSQL como service container do próprio Actions e roda
   `poetry run python manage.py test`
3. **`build`** — autentica no Amazon ECR e builda a imagem Docker; em `push` para `main`
   publica com a tag `github.sha`, em `pull_request` builda sem publicar (validação apenas)
4. **`deploy-staging`** — dispara automaticamente a cada push em `main` (via SSH)
5. **`deploy-producao`** — mesma imagem, mas com aprovação manual obrigatória via GitHub
   Environment `producao` (*required reviewers*) — nunca deploy direto para produção

Dispara em `push` e `pull_request` para `main`; `pull_request` roda lint/testes/build mas nunca
deploy.

---

## Deploy (staging e produção)

Staging e produção rodam como duas stacks Docker Compose independentes em **uma única
instância EC2** (trade-off documentado em [Decisões técnicas](#decisões-técnicas)), cada uma
com seu próprio diretório, `.env` e banco PostgreSQL isolado:

```
/opt/lacrei/
├── staging/    (docker-compose.yml + .env — porta 8001)
├── producao/   (docker-compose.yml + .env — porta 8000)
└── nginx/conf.d/  (um server block por subdomínio)
```

- **Registry de imagens:** Amazon ECR, versionado pela tag do commit (`github.sha`) — nunca
  `latest` como única tag
- **Reverse proxy:** Nginx, roteando por subdomínio (`staging.api-lacrei.vinisolucoes.com` /
  `api-lacrei.vinisolucoes.com`) para as portas internas de cada ambiente
- **HTTPS:** obrigatório nos dois ambientes, certificado Let's Encrypt via Certbot
- **Autenticação da instância no ECR:** IAM Role (Instance Profile) anexada à EC2 — a
  instância se autentica via `sts:assumed-role`, **sem nenhuma chave de acesso AWS gravada em
  disco** (ver `docs/AWS-HARDENING.md`)
- Referências reais (sincronizadas do que roda na instância) em [`deploy/staging/`](deploy/staging/),
  [`deploy/producao/`](deploy/producao/) e [`deploy/nginx/conf.d/`](deploy/nginx/conf.d/)

O deploy consiste em: puxar a nova imagem do ECR (`docker compose pull web`) e recriar os
containers aguardando o healthcheck confirmar saúde (`docker compose up -d --wait
--wait-timeout 60`) — nunca rebuild na instância, sempre a mesma imagem já buildada e testada
no CI.

---

## Rollback

Reaponta o ambiente para uma tag de imagem anterior já publicada no ECR e recria o container —
nunca depende de rebuild:

```bash
# Na instância, dentro da pasta do ambiente (ex: /opt/lacrei/producao)
export ECR_REGISTRY=<registry>
export IMAGE_TAG=<sha-da-versao-anterior-conhecida-boa>
docker compose pull web
docker compose up -d --wait --wait-timeout 60
```

Esse é o procedimento **realmente testado**, não apenas descrito: em staging, a imagem foi
revertida deliberadamente para uma versão anterior a uma correção conhecida (reproduzindo de
propósito o problema que ela corrigia), confirmando que o healthcheck detecta a regressão
(`unhealthy`); em seguida a imagem correta foi restaurada, voltando a `healthy` em ~24 segundos
sem nenhuma intervenção manual além do próprio comando. Detalhe completo em
[`docs/SDD-07-DEPLOY-AWS.md`](docs/SDD-07-DEPLOY-AWS.md), seção "Correções pós-implementação",
item 6.

---

## Decisões técnicas

| Decisão | Justificativa | Referência |
|---|---|---|
| `on_delete=PROTECT` em `Consulta → Profissional` | Evita perda silenciosa de histórico de consultas — dado de saúde não pode desaparecer numa exclusão em cascata | SDD-02 |
| Autenticação obrigatória também em `GET` | Vai além do mínimo pedido pelo desafio, mas dados de profissionais/consultas de saúde não devem ficar públicos mesmo em leitura | SDD-04 |
| Rate limiting com throttle dedicado ao login (5/min, mais restritivo que os 20/min anônimos padrão) | `/api/token/` é alvo natural de força bruta | SDD-04 |
| Hierarquia própria de exceções de domínio (`ErroAplicacao` e subclasses) em vez de `rest_framework.exceptions.ValidationError` direto | Desacopla regra de negócio do framework web (SOLID "D") — a tradução para status HTTP fica centralizada em um único `match/case` (`tratar_erro_global`), nunca espalhada por view; a exceção de domínio continua utilizável mesmo fora de um contexto HTTP | `CONVENCOES-CODIGO.md`, seção 4 |
| EC2 única para staging + produção | Prazo do desafio (5 dias úteis); separação lógica por diretório/container/domínio, não física — em produção real com tráfego, staging e produção usariam instâncias/contas separadas e RDS gerenciado | SDD-07 |
| IAM Role (Instance Profile) na EC2, sem chave de acesso estática em disco | Reduz superfície de ataque: a instância se autentica no ECR via `sts:assumed-role`, sem credencial AWS gravada na máquina — mesmo custo de setup que uma chave estática | `docs/AWS-HARDENING.md` |
| Rollback via retag de imagem já publicada no ECR | Evita rebuild — restaura uma versão já testada em minutos, não depende do CI estar disponível no momento do incidente | SDD-07 |

---

## Limitações conhecidas

Decisões conscientes de escopo dado o prazo do desafio, não bugs nem esquecimentos:

- **CloudWatch (logs/alarmes) não implementado** — logs ficam em `docker logs`, já em JSON
  estruturado (SDD-04), suficiente para debug manual nesta fase.
- **EC2 única para staging + produção**, em vez de instâncias/contas separadas — ver
  [Decisões técnicas](#decisões-técnicas) e SDD-07 para o trade-off completo.
- **Processamento assíncrono (Celery/Redis) não implementado** — candidato natural de evolução
  para notificações de consulta, não necessário para o escopo de CRUD deste desafio.
- **Backup automatizado não implementado** (snapshot do EBS + `pg_dump` para S3) — risco aceito
  dado que não há dado real de produção nesta fase de avaliação. Ver `docs/AWS-HARDENING.md`.
- **OIDC entre GitHub Actions e AWS adiado** — usuário IAM com chave de acesso estática, mas com
  policy restrita ao ARN específico do repositório ECR (reduz o risco principal, mantém o
  secundário). Ver `docs/AWS-HARDENING.md` para a ordem de prioridade de itens adiados caso o
  projeto evolua para uso real e contínuo.
- **AWS Systems Manager (SSM) adiado** — SSH tradicional com porta 22 aberta (ver
  [Decisões técnicas](#decisões-técnicas)) em vez de eliminar a porta por completo via SSM.

---

## Metodologia de desenvolvimento

Este projeto foi desenvolvido usando **Spec-Driven Development (SDD)**, com apoio do Claude
Code no processo de implementação. Cada funcionalidade tem uma especificação própria — Regra de
Negócio (RN) → Critério de Aceite (CA) → Teste — escrita **antes** do código, documentada em
[`docs/`](docs/):

| SDD | Título |
|---|---|
| [SDD-01](docs/SDD-01-SETUP-PROJETO.md) | Setup do Projeto |
| [SDD-02](docs/SDD-02-MODELAGEM-DE-DADOS.md) | Modelagem de Dados |
| [SDD-03](docs/SDD-03-CRUD.md) | CRUD |
| [SDD-04](docs/SDD-04-SEGURANCA-AUTENTICACAO.md) | Segurança e Autenticação |
| [SDD-05](docs/SDD-05-TESTES.md) | Testes Automatizados |
| [SDD-06](docs/SDD-06-PIPELINE-CICD.md) | Pipeline CI/CD |
| [SDD-07](docs/SDD-07-DEPLOY-AWS.md) | Deploy AWS |
| [SDD-08](docs/SDD-08-DOCUMENTACAO-API.md) | Documentação da API (bônus) |
| [SDD-09](docs/SDD-09-README-ROLLBACK.md) | README, Decisões e Rollback (este documento) |

Documentos de apoio, fora da numeração SDD por não serem especificação de funcionalidade:
[`docs/CLAUDE.md`](docs/CLAUDE.md) (convenções obrigatórias e histórico de sessões),
[`docs/docs-visao-geral.md`](docs/docs-visao-geral.md) (arquitetura e glossário),
[`docs/CONVENCOES-CODIGO.md`](docs/CONVENCOES-CODIGO.md) (estrutura OO, hierarquia de
exceções), [`docs/QA-01-SMOKE-LACREI.md`](docs/QA-01-SMOKE-LACREI.md) (validação end-to-end
contra container real) e [`docs/AWS-HARDENING.md`](docs/AWS-HARDENING.md) (ADR de hardening de
infraestrutura, adotado vs. adiado).

Parte do processo incluiu múltiplas rodadas de **auditoria de consistência entre os SDDs**
(conferindo se um SDD posterior não contradizia decisões já fechadas em um anterior — ex:
nomenclatura de variável, formato de resposta de erro) antes de cada fase ser implementada, não
apenas escrita.

### Matriz de rastreabilidade

| Critério do desafio | SDD correspondente |
|---|---|
| CRUD funcional + busca por ID do profissional | SDD-02, SDD-03 |
| Segurança (sanitização, CORS, autenticação, SQL Injection) | SDD-04 |
| Docker + PostgreSQL | SDD-01 |
| GitHub Actions (CI/CD) | SDD-06 |
| Deploy staging + produção | SDD-07 |
| Testes automatizados + erro | SDD-05 |
| README + rollback | SDD-09 (este documento) |
| Documentação da API (bônus) | SDD-08 |

---

## Estrutura do repositório

```
lacrei-desafio/
├── README.md
├── docs/                        ← SDDs, convenções, ADRs (ver Metodologia)
├── .env.example
├── .gitignore
├── .dockerignore
├── pyproject.toml
├── poetry.lock
├── docker-compose.yml
├── Dockerfile
├── docker-entrypoint.sh
├── manage.py
├── .github/
│   └── workflows/
│       └── ci-cd.yml
├── deploy/                      ← cópias de referência do que roda de fato na EC2 (SDD-07)
│   ├── staging/docker-compose.yml
│   ├── producao/docker-compose.yml
│   └── nginx/conf.d/
├── config/
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/
│   │   ├── constantes.py
│   │   ├── exceptions.py        ← ErroAplicacao e subclasses (ver CONVENCOES-CODIGO.md)
│   │   ├── exception_handler.py ← tratar_erro_global, match/case
│   │   ├── logging.py           ← FormatadorJSON
│   │   ├── middleware.py        ← MiddlewareLogAcesso
│   │   ├── throttling.py        ← ThrottleLogin
│   │   ├── utils.py
│   │   └── views.py             ← health check
│   ├── profissionais/
│   │   ├── models.py / serializers.py / views.py / admin.py
│   │   └── migrations/
│   └── consultas/
│       ├── models.py / serializers.py / views.py / admin.py
│       └── migrations/
└── tests/
    ├── base.py                  ← APITestCaseAutenticado
    ├── profissionais/           ← test_crud.py, test_erros.py + fixtures/
    ├── consultas/                ← test_crud.py, test_erros.py, test_refinamentos.py + fixtures/
    ├── seguranca/                ← autenticação, rate limiting, CORS, health check + fixtures/
    ├── integracao/                ← fluxo completo profissional ↔ consulta + fixtures/
    ├── regressao/                 ← bugs reais corrigidos, documentados + fixtures/
    ├── contrato/                  ← formato estável de resposta JSON + fixtures/
    └── fixtures/dados_compartilhados.json  ← identidades fixas reaproveitadas entre módulos
```
