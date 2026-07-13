# Visão Geral — API de Gerenciamento de Consultas Médicas (Lacrei Saúde)
> Este documento muda raramente. Ele é o contexto estático que qualquer sessão nova do
> Claude Code deve ler primeiro (ver CLAUDE.md, seção 1). Regras de negócio específicas,
> critérios de aceite e detalhes de implementação vivem nos SDDs — aqui só o panorama.

---

## 1. Contexto do desafio

Este projeto é a resposta ao desafio técnico de voluntariado da **Lacrei Saúde**, uma
organização que amplia o acesso à saúde inclusiva para a comunidade LGBTQIAPN+. A missão é
construir uma **API RESTful de Gerenciamento de Consultas Médicas** — CRUD de profissionais
da saúde e das consultas vinculadas a eles — com qualidade de produção: segurança, testes,
CI/CD e deploy funcional, não apenas um protótipo.

O projeto foi desenvolvido com metodologia **Spec-Driven Development (SDD)**: toda
funcionalidade tem uma especificação (Regra de Negócio → Critério de Aceite → Teste) escrita
**antes** do código, com apoio do Claude Code na implementação. Ver seção 7 para o índice
completo dos SDDs.

---

## 2. Arquitetura em uma imagem

```
                        ┌─────────────────────────────┐
                        │      Cliente HTTP (curl,      │
                        │   Swagger UI, Postman, etc.)  │
                        └──────────────┬───────────────┘
                                       │ HTTPS
                                       ▼
                        ┌─────────────────────────────┐
                        │   Nginx (reverse proxy)       │  ← só em staging/produção (SDD-07)
                        │   staging.<dominio> / <dominio>│
                        └──────────────┬───────────────┘
                                       ▼
              ┌───────────────────────────────────────────────┐
              │              Django + DRF (Gunicorn)             │
              │                                                 │
              │  urls.py (router)                                │
              │     │                                            │
              │     ├── /api/token/, /api/token/refresh/  ── PÚBLICO (AllowAny)
              │     ├── /health/                          ── PÚBLICO (AllowAny)
              │     ├── /api/schema/, /docs/, /redoc/      ── PÚBLICO (AllowAny)
              │     └── /api/profissionais/, /api/consultas/ ── PROTEGIDO (JWT obrigatório)
              │            │
              │            ▼
              │     MiddlewareLogAcesso  →  logs JSON estruturados (stdout)
              │            │
              │            ▼
              │     ViewSet (ModelViewSet do DRF)
              │            │
              │            ▼
              │     Serializer (validação de entrada/saída, RN combinadas)
              │            │
              │            ▼
              │     Model (Django ORM — única camada que toca o banco)
              └───────────────────────────┬─────────────────────┘
                                          ▼
                        ┌─────────────────────────────┐
                        │        PostgreSQL              │
                        │   (Profissional, Consulta,     │
                        │    tabelas de auth do Django)  │
                        └─────────────────────────────┘
```

**Leitura da imagem:** toda requisição passa pelo mesmo funil — roteamento → middleware de
log → view → serializer → model. Não existe atalho: uma view nunca toca o banco direto sem
passar pelo model, e uma regra de validação nunca vive dentro do model (isso é decisão
deliberada, ver seção 4).

---

## 3. Fronteiras entre apps Django

O projeto tem três apps, cada um com responsabilidade única e sem sobreposição:

| App | Responsabilidade | Pode depender de | Nunca depende de |
|---|---|---|---|
| `apps/core` | Infraestrutura transversal: health check, logging JSON, exception handler, middleware de acesso, throttling, constantes globais | Nada (é a base) | `profissionais`, `consultas` |
| `apps/profissionais` | Model, serializer e view de `Profissional` | `apps/core` (constantes, exception handler) | `apps/consultas` |
| `apps/consultas` | Model, serializer e view de `Consulta` | `apps/core`, e referencia `profissionais.Profissional` via FK | Nada além disso |

**Regra de dependência:** a seta de dependência é sempre `consultas → profissionais → core`,
nunca o inverso. Isso significa, por exemplo, que `apps/profissionais` **não pode** importar
nada de `apps/consultas` — se um dia isso parecer necessário, é sinal de que a lógica está no
lugar errado (provavelmente deveria estar em `apps/core` ou num serviço compartilhado).

`config/` (settings, urls raiz) não é um app — é a cola que registra os outros três.

---

## 4. Onde vive cada tipo de lógica

Esta é a regra mais importante do projeto para manter o código organizado — e a que mais
gera confusão se não for lida com atenção:

| Tipo de lógica | Vive em | Nunca vive em | Por quê |
|---|---|---|---|
| Estrutura de dados, constraints, `on_delete` | `models.py` | `serializers.py`, `views.py` | Definido no SDD-02 — é a "lei permanente" do dado |
| Validação de campo único (obrigatório, tamanho) | `serializers.py` (`Meta.fields`, validators nativos do DRF) | `models.py`, `views.py` | Validação de entrada é responsabilidade do serializer |
| Validação combinada entre campos (ex: "email ou telefone") | `serializers.py` (`def validate(self, dados)`) | `models.py` | Regra de negócio que envolve mais de um campo — não é constraint estrutural de banco |
| Roteamento HTTP, status code, paginação | `views.py` (ViewSet) | `serializers.py` | View decide *como* responder, serializer decide *o que* é válido |
| Autenticação, permissões, throttling | `settings.py` (global) + override pontual em views específicas (ex: `TokenObtainPairViewPublica`) | Espalhado em cada view individualmente | Configuração global evita esquecer de proteger uma rota nova |
| Constantes numéricas/strings de configuração | `apps/core/constantes.py` | Hardcoded em qualquer arquivo | Zero números mágicos — rastreável até o SDD de origem |
| Erro de regra de negócio (conflito, exclusão protegida) | Exceção de domínio própria (`apps/core/exceptions.py`, `ErroAplicacao` e subclasses — ver `CONVENCOES-CODIGO.md`) | `rest_framework.exceptions.ValidationError` levantada diretamente em service/serializer | Tradução para status HTTP é centralizada em um único `match/case` (`tratar_erro_global`), nunca espalhada |
| Logging | `logger.info(..., extra={...})` em qualquer módulo, formato definido uma vez em `apps/core/logging.py` | `print()` em qualquer lugar | Logs precisam ser JSON estruturado (SDD-04, RN-16) |

**Teste rápido ao escrever código:** se uma linha de validação está dentro de um `models.py`,
ou uma constante numérica está solta em um `views.py`, algo está no lugar errado — voltar ao
SDD correspondente antes de prosseguir.

---

## 5. Fluxo de uma requisição autenticada (exemplo concreto)

Para tornar a arquitetura da seção 2 mais tangível, este é o caminho completo de um
`POST /api/consultas/` bem-sucedido:

1. Cliente envia `POST /api/consultas/` com header `Authorization: Bearer <token>` e corpo
   `{"profissional": "<uuid>", "data_hora": "2026-08-01T10:00:00Z"}`
2. Nginx (só em staging/produção) repassa a requisição para o Gunicorn
3. `MiddlewareLogAcesso` marca o timestamp de início
4. DRF valida o JWT (`JWTAuthentication`) — se inválido/ausente, retorna `401` aqui e o fluxo para
5. DRF verifica `IsAuthenticated` — já satisfeito pelo passo anterior
6. `ConsultaViewSet.create()` (herdado do `ModelViewSet`) delega para `ConsultaSerializer`
7. `ConsultaSerializer.validate()` verifica conflito de horário (SDD-03, RN-11) — se houver
   conflito, levanta `ErroConflitoHorario` (exceção de domínio, não uma validação solta)
8. Serializer válido → `Consulta.objects.create(...)` — aqui a constraint de banco
   (`UniqueConstraint`) age como segunda barreira, redundante mas intencional
9. Resposta `201` serializada de volta ao cliente
10. `MiddlewareLogAcesso` calcula a duração e emite um log JSON: `{"ts": ..., "nivel": "INFO",
    "modulo": "...", "mensagem": "Requisição processada", "path": "/api/consultas/",
    "metodo": "POST", "status": 201, "usuario": "...", "duracao_ms": 12.4}`

Se `ErroConflitoHorario` (ou qualquer outra exceção de domínio) for levantada em qualquer
ponto, ela chega ao `tratar_erro_global` (SDD-04), que faz `match/case` sobre o tipo da
exceção e traduz para o status HTTP correto (`400`, `404`, etc.) num único lugar — nenhuma
view decide isso por conta própria (ver `CONVENCOES-CODIGO.md`, seção 4). Se for uma exceção
verdadeiramente inesperada (não mapeada), o mesmo handler loga o stack trace completo no
servidor e retorna `500` genérico ao cliente, sem vazar detalhe interno.

---

## 6. Glossário de domínio

| Termo | Significado no contexto deste projeto |
|---|---|
| **Profissional** | Pessoa profissional da saúde cadastrada no sistema (nome social, profissão, registro de classe, contato, endereço). Não é o "usuário" que autentica na API — é um registro de dados, não uma conta. |
| **Consulta** | Um agendamento de consulta médica vinculado a um profissional, com data e hora. Não confundir com "conversa" ou "sessão" — é puramente um registro de agenda. |
| **Registro profissional** | Identificador de classe (CRM, CRP, COREN, etc.) — obrigatório, sem validação de formato específico nesta fase (SDD-02, RN-11). |
| **Exclusão protegida** | Regra em que um `Profissional` com `Consulta`s vinculadas não pode ser excluído (`on_delete=PROTECT`) — decisão de integridade de dados de saúde, não apenas técnica (SDD-02, RN-04). |
| **Endpoint público** | As únicas 5 rotas isentas de autenticação: `/api/token/`, `/api/token/refresh/`, `/health/`, `/api/schema/`, `/api/docs/`, `/api/redoc/` — todas as demais exigem JWT válido, inclusive leitura (SDD-04, RN-02 e RN-15). |
| **Ambiente** | "Staging" e "produção" — duas instâncias lógicas da aplicação (containers/domínios distintos), rodando na mesma instância EC2 por decisão de escopo do desafio (SDD-07). Não confundir com "development", que é o ambiente local do desenvolvedor. |
| **Rollback** | Reapontar o `docker-compose` do ambiente para uma tag de imagem anterior já publicada no ECR e recriar o container — nunca envolve rebuild (SDD-07, RN-07). |

---

## 7. Índice dos SDDs

| SDD | Título | O que define |
|---|---|---|
| SDD-01 | Setup do Projeto | Poetry, Docker, PostgreSQL, settings por ambiente, prontidão para AWS |
| SDD-02 | Modelagem de Dados | Models de `Profissional` e `Consulta`, constraints, índices |
| SDD-03 | CRUD | Serializers, ViewSets, routers, busca por profissional, refinamentos (conflito de horário, `select_related`, filtro de data) |
| SDD-04 | Segurança e Autenticação | JWT, CORS, rate limiting, exceções de rota pública, logging JSON |
| SDD-05 | Testes Automatizados | CRUD, erro, integração (B2B), regressão, contrato |
| SDD-06 | Pipeline CI/CD | GitHub Actions: lint, teste, build, deploy |
| SDD-07 | Deploy AWS | Staging + produção em EC2, ECR, Nginx, rollback |
| SDD-08 | Documentação da API (bônus) | Swagger/Redoc via `drf-spectacular` |
| SDD-09 | README, Decisões e Rollback | Documento final de síntese para o avaliador |

Documentos de apoio (fora da numeração SDD, pois não são especificação de funcionalidade):

| Documento | Papel |
|---|---|
| `CLAUDE.md` | Convenções obrigatórias, checklist de fase, prompt de continuidade entre sessões |
| `docs/visao-geral.md` (este arquivo) | Contexto e arquitetura estáticos |
| `docs/decisoes/CONVENCOES-CODIGO.md` | Estrutura OO, controle de fluxo, hierarquia de exceções — como o código é escrito, não o que ele faz |
| `QA-01-SMOKE-LACREI.md` | Validação end-to-end contra o container real, após SDD-01 a SDD-04 |
| `AUDITORIA-SDD-01-A-09.md` | Histórico de revisões de consistência entre os SDDs |

---

## 8. O que este projeto deliberadamente não é

Para evitar escopo criativo durante a implementação, vale registrar o que este projeto **não**
tenta ser, mesmo que tecnicamente possível:

- **Não é** um sistema de verificação de disponibilidade/agenda (não calcula horários livres,
  não sugere slots) — apenas armazena e recupera o que já foi decidido no payload.
- **Não é** um sistema com processamento assíncrono de notificações (fila, Celery) — cogitado
  como evolução futura, não implementado nesta entrega (ver SDD-09, limitações conhecidas).
- **Não é** multi-tenant — assume um único conjunto de dados, sem isolamento por
  cliente/organização.
- **Não tem** integração de pagamento implementada — apenas uma eventual proposta de
  arquitetura (Asaas), se sobrar tempo, e nunca antes dos itens obrigatórios.
