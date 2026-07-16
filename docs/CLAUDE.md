# CLAUDE.md — API de Gerenciamento de Consultas Médicas (Lacrei Saúde)

Leia este arquivo **inteiro** antes de qualquer ação. Ele é sua fonte de verdade para este projeto.

---

## 1. Antes de começar qualquer etapa

1. Leia `docs/docs-visao-geral.md` — contexto, escopo, arquitetura, glossário de domínio.
2. Leia `docs/CONVENCOES-CODIGO.md` — estrutura OO, controle de fluxo, hierarquia de exceções. Aplica-se a qualquer etapa a partir do SDD-03.
3. Leia `docs/SDD-01-SETUP-PROJETO.md` — aplica-se a qualquer etapa que toque configuração, Docker ou ambiente.
4. Leia `docs/SDD-02-MODELAGEM-DE-DADOS.md` — aplica-se a qualquer etapa que toque models, migrations ou banco.
5. Leia o SDD da etapa atual (indicado na seção 4).
6. Só então implemente — nunca antes.

Se dois SDDs conflitarem, o SDD da etapa atual prevalece. Se conflitarem com o SDD-01 ou SDD-02, sinalize antes de prosseguir — pode ser inconsistência nos docs.

---

## 2. Convenções obrigatórias (violação = reescrever)

### Nomenclatura
- **Funções, métodos, variáveis, classes, campos de model e serializers: português, autoexplicativos**
  - ✓ `criar_profissional`, `buscar_consultas_por_profissional`, `validar_contato_preenchido`
  - ✗ `createProfessional`, `getAppointments`, `validate_contact`
- **Timestamps de auditoria também em português:** `criado_em`, `atualizado_em` — sem exceção (ver SDD-02)
- **Arquivos Python:** `snake_case.py`
- **Apps Django:** nomes em português, plural (`profissionais`, `consultas`)
- **URLs de API:** em português, seguindo o recurso (`/api/profissionais/`, `/api/consultas/`)

### Tipos e schemas
- **Serializers do DRF** são a fonte única de verdade para validação de entrada/saída — zero validação manual solta em views
- Um serializer por responsabilidade: não reaproveitar o mesmo serializer para criação e listagem se as regras de campo divergirem
- Validações combinadas de campo (ex: "email ou telefone obrigatório" — RN-08 do SDD-02) vivem em `validate()` do serializer, nunca no model

### Constantes
- **Zero números mágicos** — toda constante em `apps/core/constantes.py`
- Toda constante tem nome autoexplicativo e comentário referenciando o SDD/seção de origem
- Exemplos esperados: `LIMITE_PAGINACAO_PADRAO`, `MAX_TENTATIVAS_LOGIN`
- **Exceção explícita:** `max_length` de campos de model (ex: `nome_social = models.CharField(max_length=255)`)
  **não** é extraído para `constantes.py` — é um limite estrutural de coluna (schema de banco), não uma
  regra de negócio configurável como `LIMITE_PAGINACAO_PADRAO` ou `MAX_TENTATIVAS_LOGIN`. Decisão revisitada
  e fechada na sessão de pente-fino de 2026-07-15 (ver `docs/SDD-02-MODELAGEM-DE-DADOS.md`, referência de
  implementação, que já hardcoda esses valores) — não reabrir essa dúvida em revisões futuras.

### Python / Django
- Type hints em funções utilitárias e métodos de serviço (views e serializers seguem convenção DRF padrão)
- Zero `except Exception` sem log com contexto
- Funções e métodos pequenos — se precisar de "e" para descrever, divida
- Early return — retorne cedo em erro/validação inválida, evite aninhamento excessivo
- Lógica de negócio não vive em `views.py` — fica em serializers ou em `services.py` quando ultrapassar validação simples

### SOLID aplicado
- **S:** cada serializer/view faz uma coisa. `ProfissionalSerializer` só valida/serializa profissional.
- **O:** novos filtros de busca entram como novo método/query param — sem alterar os existentes.
- **L:** qualquer `ViewSet` customizado deve continuar compatível com o contrato REST padrão do DRF.
- **I:** serializers de entrada e saída separados quando as regras de campo divergirem.
- **D:** views recebem dependências (querysets, permissões) via configuração de classe — nunca lógica hardcoded dentro do método.

### Banco de dados — Regra Absoluta
- **Sempre** via Django ORM — nunca SQL raw com f-string ou concatenação (proteção nativa contra SQL Injection)
- Se SQL raw for estritamente necessário em algum ponto, usar apenas com parâmetros (`params=[...]`), nunca interpolação de string
- `on_delete` de toda FK é uma decisão documentada no SDD correspondente, nunca default silencioso (ver RN-04/RN-09 do SDD-02)
- Migrations sempre geradas via `makemigrations` — nunca editadas manualmente sem justificativa documentada

### Padrão Guard (aplicado nas camadas de serviço/exceção)
```python
# Guard A — crítico: exceção propaga para o exception_handler global do DRF
profissional = Profissional.objects.get(pk=id_profissional)

# Guard B — não crítico: retorna fallback em caso de erro esperado
try:
    consultas = Consulta.objects.filter(profissional=profissional)
except Consulta.DoesNotExist:
    logger.warning(f"[GUARD-B:consultas] profissional {id_profissional} sem consultas")
    consultas = Consulta.objects.none()

# Guard C — silencioso: loga e continua sem interromper o fluxo
try:
    registrar_log_acesso(request)
except Exception as e:
    logger.error(f"[GUARD-C:log_acesso] {e} — continuando")
```

### Segurança
- Autenticação obrigatória em todas as rotas de escrita (POST/PUT/PATCH/DELETE) — ver SDD-04
- CORS restrito às origens configuradas via `.env` — nunca `*`
- Nenhum segredo com valor default em `settings/base.py` ou `production.py`
- Sanitização e validação de entrada sempre via serializer, nunca confiando em dado bruto do `request.data`
- Logs de acesso e erro estruturados, sem registrar senha, token ou dado sensível de paciente/profissional em texto livre

### Testes
- `APITestCase` do DRF para todos os testes de endpoint
- Todo teste de erro verifica o **status code correto** e a **mensagem de erro relevante**, não apenas "não é 200"
- Nenhum teste depende de ordem de execução ou de estado deixado por outro teste (setup/teardown isolado)
- **Dados de teste (payload, endpoint, nome de campo) vivem em `fixtures/<modulo>_test_data.json`**, ao lado do(s) arquivo(s) de teste que os usam, carregados via `carregar_dados_teste(__file__, "...")` (`tests/base.py`) — nunca magic string solta no corpo do teste. Exceção: mensagens de erro esperadas verificadas via `assertIn` (ex: `"vinculadas"`) continuam literais no teste — são a própria asserção validada contra `apps/core/exceptions.py`, não um dado de entrada; duplicá-las no JSON criaria uma segunda fonte de verdade que pode ficar dessincronizada da mensagem real.
- **Dados idênticos reaproveitados por mais de um módulo** vivem em `tests/fixtures/dados_compartilhados.json`, carregados via `carregar_dados_compartilhados()`. Cada chave nesse arquivo (ex: `profissionais.ana_souza`, `profissionais.carla_lima`) representa uma **identidade fixa e imutável** — o mesmo profissional/consulta, com os mesmos dados, em todo lugar onde a chave é referenciada. **Nunca** reaproveite uma chave compartilhada para um payload só "parecido" ou "quase igual"; se um teste precisa de uma variação (outro campo, outro valor, mesmo que seja "a mesma pessoa" conceitualmente com um dado diferente), crie uma entrada local nova no `fixtures/<modulo>_test_data.json` daquele módulo, com um nome que deixe a diferença óbvia — nunca um novo teste "pegando emprestado" `ana_souza`/`carla_lima` e sobrescrevendo um campo por fora. Exemplo real: o profissional de `tests/integracao/` é a mesma "Carla Lima"/CRM-9876 mas com `telefone` em vez de `email` — por isso ele é uma entrada **local** (`profissional_carla` em `integracao_test_data.json`), não a chave compartilhada `carla_lima`.

---

## 3. O que você NUNCA deve fazer

| Proibido | Motivo |
|---|---|
| Nomes de função/campo em inglês (exceto termos técnicos de framework) | Viola convenção do projeto |
| Números mágicos fora de `constantes.py` | Viola rastreabilidade |
| SQL raw com f-string ou concatenação | SQL Injection |
| `on_delete=CASCADE` sem decisão documentada no SDD | Perda de dados não intencional |
| Validação de negócio dentro do `models.py` | Viola separação model/serializer definida no SDD-02 |
| CORS com origin `*` | Falha de segurança |
| Valor default para segredo em settings | Falha silenciosa de segurança |
| Commitar `.env` real | Exposição de credenciais |
| Rota de escrita sem autenticação | Viola critério de aceite obrigatório do desafio |
| Esquecer `AllowAny` explícito em `/api/token/`, `/health/` ou rotas de docs | Sem essa exceção, ninguém consegue obter o primeiro token (SDD-04, RN-15) — quebra a aplicação inteira |
| Criar app/arquivo fora da estrutura definida | Desorganização |
| Implementar algo não especificado no SDD atual | Escopo não validado |
| Editar migration já aplicada em vez de criar uma nova | Quebra histórico de schema |

---

## 4. Etapa atual

```
STATUS:    FASE 5 (SDD-05) CONCLUÍDA — suíte de testes automatizados completa,
           40 testes, 0 falhas, 0 erros, 0 pulados (2026-07-14). CORREÇÕES DE
           PENTE-FINO aplicadas em cima do relatório de auditoria da sessão
           anterior (2026-07-15/16) — ver ETAPA abaixo. Suíte segue em 40/40
           após as correções (nenhum teste novo, um teste existente ajustado).
ETAPA:     Sessão de correções de pente-fino (não é uma fase nova do SDD):
           (1) .dockerignore criado na raiz (.env, .env.*, .git, .gitignore,
           __pycache__/, *.pyc, tests/, docs/, .ruff_cache/, staticfiles/) —
           evita segredo (.env) e histórico .git dentro da imagem Docker.
           ATENÇÃO: isso também remove tests/ da imagem final — quebra
           `docker-compose exec web python manage.py test` depois de um
           rebuild; ver nota de atenção abaixo. (2) apps/core/views.py —
           health check agora loga erro (logger "lacrei.saude", exc_info=True)
           antes do 503, em vez de engolir a exceção silenciosamente.
           (3) config/settings/production.py — hardening HTTPS/cookies
           (SECURE_SSL_REDIRECT, SESSION_COOKIE_SECURE, CSRF_COOKIE_SECURE,
           SECURE_HSTS_SECONDS, SECURE_PROXY_SSL_HEADER), preparando para o
           ALB do SDD-07. (4) ProfissionalSerializer.validate() (RN-03,
           email/telefone) migrado de serializers.ValidationError direto para
           ErroValidacao (apps/core/exceptions.py) — mesmo tratamento que
           ConsultaSerializer já dava ao conflito de horário; resposta mudou
           de {"contato": [...]} para {"detail": "..."} — teste
           tests/profissionais/test_erros.py ajustado. (5) apps/core/utils.py
           criado com valor_efetivo(dados, instancia, campo, default) —
           elimina a duplicação do padrão dados.get(campo,
           getattr(instancia, campo, default)) entre ProfissionalSerializer e
           ConsultaSerializer. (6) ruff e black adicionados como
           [tool.poetry.group.dev.dependencies] no pyproject.toml, com
           [tool.ruff]/[tool.black] em line-length=100 (alinhado ao
           CONVENCOES-CODIGO.md) — poetry.lock regenerado. (7) `black .`
           rodado em todo o repositório (23 arquivos reformatados, sem
           mudança de lógica). (8) Status HTTP literais (500/400/404/503)
           substituídos por rest_framework.status.HTTP_* em
           apps/core/exceptions.py, exception_handler.py e views.py.
           (9) tests/seguranca/test_cors_e_erros.py corrigido para usar
           status.HTTP_500_INTERNAL_SERVER_ERROR. (10) Decisões fechadas
           documentadas: CLAUDE.md seção "Constantes" agora registra
           explicitamente que max_length de model é limite estrutural de
           coluna, não extraído para constantes.py; ErroRecursoNaoEncontrado
           (apps/core/exceptions.py) ganhou docstring explicando que está
           reservada para um futuro lookup por campo não-PK, não deve ser
           removida. Verificação final: ruff check limpo, black --check limpo,
           40/40 testes passando (confirmado após rebuild da imagem web com o
           poetry.lock atualizado), health check com banco desligado
           reproduzido via `docker compose stop db` — log ERRO
           "Health check falhou: conexão com banco indisponível" com stack
           trace completo confirmado via `docker logs`.
           PONTO DE ATENÇÃO (achado nesta sessão, fora do escopo das 10
           correções pedidas): docker-entrypoint.sh ignora qualquer comando
           passado (`"$@"`) — sempre executa `exec gunicorn ...`
           incondicionalmente. Isso significa que `docker run <imagem>
           <comando>` / `docker compose run web <comando>` nunca rodam o
           comando pedido, só sobem outro gunicorn. `docker-compose exec web
           python manage.py test` continua funcionando (exec entra num
           container já rodando, não passa pelo entrypoint), mas só enquanto
           tests/ estiver presente na imagem — o que deixou de ser verdade
           depois da correção (1) acima. Decisão pendente para o SDD-06: como
           a CI vai rodar a suíte (imagem separada para test, stage dedicado
           no Dockerfile, ou ajustar docker-entrypoint.sh para respeitar
           "$@" via `exec "$@"`).
SDDs:      Todos escritos e auditados (01 Setup, 02 Modelagem, 03 CRUD+refinamentos,
           04 Segurança, 05 Testes, 06 CI/CD, 07 Deploy AWS, 08 Swagger, 09 README)
PRÓXIMA:   Fase 6 — SDD-06 (Pipeline CI/CD): GitHub Actions rodando lint → test →
           build → deploy em sequência, falhando corretamente se algum step falhar.
           Resolver o ponto de atenção do docker-entrypoint.sh (acima) como parte
           do design do step de test/build do SDD-06.
```

### Sequência completa de desenvolvimento

| Fase | SDD | Entrega | Dependências |
|---|---|---|---|
| **1 — Setup** | SDD-01 | `pyproject.toml`, `docker-compose.yml`, `Dockerfile`, `settings/` divididos, `.env.example`, health check | Nenhuma |
| **2 — Modelagem** | SDD-02 | `apps/profissionais/models.py`, `apps/consultas/models.py`, migrations | Fase 1 |
| **3 — CRUD** | SDD-03 | Serializers, ViewSets, routers — CRUD completo + busca por ID do profissional | Fase 2 |
| **4 — Segurança** | SDD-04 | Autenticação (JWT/Token), CORS, permissions | Fase 3 |
| **5 — Testes** | SDD-05 | `APITestCase` cobrindo CRUD + casos de erro | Fases 3 e 4 |
| **6 — CI/CD** | SDD-06 | GitHub Actions: lint, test, build, deploy | Fase 5 |
| **7 — Deploy AWS** | SDD-07 | Staging + produção funcionais | Fase 6 |
| **8 — Documentação da API** | SDD-08 (bônus) | Swagger/Redoc | Fase 3 (pode rodar em paralelo às fases 4-7) |
| **9 — README e Rollback** | SDD-09 | README completo, decisões técnicas, proposta de rollback | Fases 1-7 |

> Quando uma fase for concluída, atualize o bloco STATUS/ETAPA/PRÓXIMA acima antes de continuar.

---

## 5. Critérios para avançar de fase

**Fase 1 (concluída — ver SDD-01)**
- [x] `docker-compose up --build` sobe sem erro
- [x] `/health/` retorna 200 com conexão ao banco confirmada
- [x] Settings divididos por ambiente, sem segredo hardcoded

**Fase 2 (concluída — ver SDD-02)**
- [x] Migrations de `Profissional` e `Consulta` aplicadas sem erro
- [x] `on_delete=PROTECT` validado via teste manual (exclusão bloqueada com consulta vinculada)
- [x] Todos os campos obrigatórios/opcionais conforme RN-01 a RN-11

**Fase 3 (concluída — ver SDD-03)**
- [x] CRUD completo de `Profissional` (criar, listar, detalhar, atualizar, excluir)
- [x] CRUD completo de `Consulta` (criar, listar, detalhar, atualizar, excluir)
- [x] Endpoint de busca de consultas por ID do profissional funcional
- [x] Serializers aplicando validação combinada de `email`/`telefone` (RN-08)
- [x] Erros de validação retornam 400 com mensagem clara por campo
- [x] Extensões: constraint de conflito de horário, `select_related`, filtro por intervalo de data (SDD-03, RN-11 a RN-14)

**Fase 4 (concluída — ver SDD-04)**
- [x] Rotas de escrita retornam 401/403 sem autenticação válida
- [x] CORS restrito ao(s) domínio(s) configurado(s) via `.env`
- [x] Nenhum dado sensível vaza em mensagem de erro de autenticação
- [x] **Atenção:** `/api/token/`, `/api/token/refresh/`, `/health/` são explicitamente públicas (`AllowAny`) — validado via curl. Rotas do `drf-spectacular` ficam pendentes para o SDD-08 (ainda não implementado)

**Fase 5 (concluída — ver SDD-05)**
- [x] Cobertura mínima definida atingida (CRUD + erros) — 40 testes, 0 falhas
- [x] Testes de erro cobrem: dados ausentes, tipo inválido, FK inexistente, exclusão protegida

**Fase 6**
- [ ] Pipeline roda lint → test → build → deploy em sequência
- [ ] Pipeline falha corretamente se algum step falhar (não avança silenciosamente)

**Fase 7**
- [ ] Ambiente de staging acessível publicamente
- [ ] Ambiente de produção acessível publicamente
- [ ] Rollback documentado e testado ao menos uma vez

**Fase 9**
- [ ] README cobre setup local, Docker, testes, deploy, decisões técnicas e rollback
- [ ] Seção sobre uso de IA/metodologia SDD incluída (conforme decidido)

---

## 6. Estrutura de documentos

> Estrutura real (flat — sem subpastas dentro de `docs/`, confirmado na Fase 1):

```
docs/
├── CLAUDE.md
├── docs-visao-geral.md                     ← leia sempre primeiro
├── CONVENCOES-CODIGO.md                    ← estrutura OO, exceções, controle de fluxo
├── SDD-01-SETUP-PROJETO.md
├── SDD-02-MODELAGEM-DE-DADOS.md
├── SDD-03-CRUD.md
├── SDD-04-SEGURANCA-AUTENTICACAO.md
├── SDD-05-TESTES.md
├── SDD-06-PIPELINE-CICD.md
├── SDD-07-DEPLOY-AWS.md
├── SDD-08-DOCUMENTACAO-API.md
├── SDD-09-README-ROLLBACK.md
└── QA-01-SMOKE-LACREI.md
```
> Todos os documentos vivem direto em `docs/`, sem subpastas `decisoes/` ou `specs/` — essas
> só existiam em versões antigas deste plano. ADRs pontuais adicionais, se surgirem, também
> entram flat em `docs/`, seguindo o padrão de nomenclatura já usado (`CONVENCOES-CODIGO.md`,
> `SDD-*`).

---

## 7. Estrutura do repositório

```
lacrei-desafio/
├── CLAUDE.md
├── docs/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── poetry.lock
├── docker-compose.yml
├── Dockerfile
├── docker-entrypoint.sh
├── manage.py
├── config/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── core/
│   │   ├── __init__.py
│   │   ├── constantes.py
│   │   ├── exceptions.py        ← ErroAplicacao e subclasses (ver CONVENCOES-CODIGO.md)
│   │   ├── views.py             ← health check (AllowAny — SDD-04, RN-15)
│   │   ├── urls.py
│   │   ├── logging.py           ← FormatadorJSON (SDD-04, RN-16)
│   │   ├── exception_handler.py ← tratar_erro_global, match/case (SDD-04, RN-17)
│   │   ├── middleware.py        ← MiddlewareLogAcesso (SDD-04)
│   │   └── throttling.py        ← ThrottleLogin (SDD-04)
│   ├── profissionais/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   ├── admin.py
│   │   └── migrations/
│   └── consultas/
│       ├── __init__.py
│       ├── models.py
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       ├── admin.py
│       └── migrations/
└── tests/
    ├── __init__.py
    ├── base.py                  ← APITestCaseAutenticado (SDD-05, RN-11)
    ├── profissionais/
    │   ├── test_crud.py
    │   └── test_erros.py
    ├── consultas/
    │   ├── test_crud.py
    │   ├── test_erros.py
    │   └── test_refinamentos.py ← SDD-03 extensões (CA-17 a CA-20)
    ├── seguranca/
    │   ├── test_autenticacao.py
    │   ├── test_rate_limiting.py
    │   └── test_health_check.py ← endpoints públicos (SDD-04, RN-15) — não herda de APITestCaseAutenticado
    ├── integracao/
    │   └── test_fluxo_profissional_consulta.py
    ├── regressao/
    │   └── test_regressao.py
    └── contrato/
        ├── test_contrato_profissionais.py
        └── test_contrato_erros.py
```

---

## 8. Stack e decisões fechadas

| Decisão | Escolha |
|---|---|
| Framework | Django + Django REST Framework |
| Gerenciador de dependências | Poetry |
| Banco | PostgreSQL (todos os ambientes — sem SQLite, ver RN-04 do SDD-01) |
| Autenticação | JWT via `djangorestframework-simplejwt`, com exceções públicas explícitas (`/api/token/`, `/health/`, docs — ver SDD-04 RN-15) |
| Estáticos em produção | Whitenoise |
| Servidor de aplicação | Gunicorn |
| Containerização | Docker + Docker Compose |
| CI/CD | GitHub Actions |
| Deploy | AWS (staging + produção) — detalhado no SDD-07 |
| Documentação da API (bônus) | `drf-spectacular` (Swagger/Redoc) |
| Modelagem de endereço | Campos estruturados (não texto livre — ver SDD-02) |
| Exclusão de profissional com consultas | Protegida (`on_delete=PROTECT`) — nunca cascata silenciosa |

---

## 9. Variáveis de ambiente obrigatórias

```env
# SDD-01 — Setup
DJANGO_SETTINGS_MODULE=config.settings.development
SECRET_KEY=
DEBUG=True
ALLOWED_HOSTS=
CSRF_TRUSTED_ORIGINS=

DATABASE_URL=
POSTGRES_DB=
POSTGRES_USER=
POSTGRES_PASSWORD=
POSTGRES_HOST=
POSTGRES_PORT=5432
# Nota: o Django só lê DATABASE_URL (via DATABASES em settings/base.py).
# Os POSTGRES_* alimentam o container `db` E o docker-compose.yml monta
# DATABASE_URL automaticamente a partir deles para o serviço `web` — não são
# duas fontes de verdade. Ver SDD-01 para o wiring completo.

# SDD-04 — Segurança e autenticação
CORS_ALLOWED_ORIGINS=
# Nota: o JWT usa o próprio SECRET_KEY do Django para assinatura (padrão do
# djangorestframework-simplejwt) — não há uma chave de assinatura separada.

# SDD-07 — Deploy AWS (apenas em staging/produção, via .env.staging / .env.production na EC2)
# Estes NÃO entram no .env local de desenvolvimento — vivem só na instância/GitHub Secrets
# AWS_ACCESS_KEY_ID=
# AWS_SECRET_ACCESS_KEY=
# AWS_REGION=
# ECR_REGISTRY=
# EC2_HOST=
# EC2_USER=
# EC2_SSH_KEY=
```

> Segredos de deploy (AWS/EC2/ECR) vivem em **GitHub Secrets**, nunca em `.env` versionado —
> listados aqui comentados apenas para referência de quais existem (ver SDD-06 e SDD-07).

---

## 10. Comandos úteis

```bash
# Desenvolvimento local (fora do Docker)
poetry install
poetry run python manage.py runserver

# Docker
docker-compose up --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py createsuperuser

# Testes
poetry run python manage.py test
poetry run python manage.py test --verbosity=2

# Verificação de convenções
grep -rn "def get_\|def handle_\|def process_" apps/ --include="*.py"   # nomes em inglês — deve retornar vazio
grep -rn "SELECT \|INSERT \|UPDATE \|DELETE " apps/ --include="*.py"     # SQL raw suspeito — revisar manualmente

# Migrations
poetry run python manage.py makemigrations
poetry run python manage.py migrate
```

---

## 11. Prompt de contexto para novo chat

```
Você está continuando o desenvolvimento da API de Gerenciamento de Consultas Médicas (desafio técnico Lacrei Saúde).
Leia o CLAUDE.md completo e os SDDs relevantes da pasta docs/ (estrutura flat, sem subpastas) antes de qualquer ação.
Não implemente nada sem ler o SDD correspondente primeiro.

## O que já foi implementado
[COLE AQUI a lista gerada ao final do chat anterior]

## Tarefa deste chat
[DESCREVA a fase ou arquivo a implementar — ex: "Implementar SDD-03: serializers, viewsets e routers de Profissional e Consulta"]
```

Ao terminar cada chat, solicite:
> "Liste todos os arquivos criados ou modificados neste chat para eu colar no próximo."

---

## 12. Como reportar ao fim de cada fase

```
✓ Fase X — [Nome] concluída

Critérios de aceite verificados:
- ✓ [critério] — [como foi testado]

Arquivos criados:
- caminho/arquivo.py — [responsabilidade em uma linha]

Arquivos modificados:
- caminho/arquivo.py — [o que mudou]

Pontos de atenção (se houver):
- [decisão fora do SDD com justificativa]
```

---

## 13. Checklist de segurança (verificar antes de qualquer commit)

- [ ] `.env` ausente do stage: `git status` não mostra `.env`
- [ ] Zero `print()` ou `logger.*` com senha, token ou dado sensível de paciente
- [ ] Zero stack trace exposto em resposta HTTP ao cliente (`DEBUG=False` em produção)
- [ ] `SECRET_KEY` sem valor default em `settings/`
- [ ] CORS com origin específica (nunca `*`)
- [ ] Toda rota de escrita exige autenticação válida
- [ ] Zero SQL raw com concatenação/f-string
- [ ] Zero nomes de função em inglês: `grep -rn "def get_\|def handle_\|def process_" apps/`
- [ ] Zero números mágicos: `grep -rn "[0-9]\+" apps/ --include="*.py" | grep -v constantes | grep -v migrations`
- [ ] Migrations commitadas correspondem exatamente ao estado atual dos models
