# SDD-06 — Pipeline CI/CD
> Leia SDD-01 e SDD-05 antes de implementar.
> Última atualização: 2026-07-09

---

## Responsabilidade

Definir o pipeline de CI/CD via GitHub Actions, cobrindo lint, testes, build da imagem Docker e deploy automatizado, com falha explícita em qualquer etapa que não passe — nenhuma etapa avança silenciosamente sobre um erro anterior.

**Não faz:** não define a infraestrutura de destino do deploy em si (SDD-07 — staging/produção na AWS). Define o fluxo de automação que dispara esse deploy.

---

## Regras de negócio

- RN-01: O pipeline roda em toda `push` para `main` e em todo `pull_request` direcionado a `main`.
- RN-02: As etapas rodam em sequência estrita: **lint → testes → build → deploy** — uma etapa só inicia se a anterior passou.
- RN-03: `pull_request` executa lint, testes e build, mas **nunca** deploy — deploy só ocorre em merge/push direto para `main` (proteção contra deploy acidental de branch não revisada).
- RN-04: O job de testes sobe um serviço PostgreSQL como *service container* do próprio GitHub Actions, isolado do banco de produção/staging.
- RN-05: Segredos (credenciais AWS, `SECRET_KEY` de produção, senha do banco) nunca aparecem em texto no workflow YAML — vêm exclusivamente de GitHub Secrets.
- RN-06: O deploy para staging ocorre automaticamente a cada push em `main`; o deploy para produção requer aprovação manual (GitHub Environments com *required reviewers*), nunca é automático direto para produção.
- RN-07: Falha em qualquer etapa cancela as etapas seguintes e marca o workflow como falho de forma visível (não é permitido `continue-on-error: true` em nenhuma etapa obrigatória).
- RN-08: O lint cobre formatação e qualidade de código Python (`ruff` ou `flake8` + `black --check`), falhando o pipeline se houver violação.
- RN-09: A imagem Docker construída no step de build é a mesma reutilizada no deploy — nunca há rebuild divergente entre CI e produção.

---

## Critérios de aceite

- CA-01: Dado um `push` para `main` com testes passando
         Quando o workflow é disparado
         Então as etapas lint, testes, build e deploy (staging) executam em sequência e todas retornam sucesso

- CA-02: Dado um `pull_request` aberto para `main`
         Quando o workflow é disparado
         Então lint, testes e build executam, e a etapa de deploy é pulada (não existe no job de PR)

- CA-03: Dado um erro de lint (ex: linha excedendo limite de caracteres, import não utilizado)
         Quando o workflow roda
         Então a etapa de lint falha e as etapas de teste/build/deploy não são executadas

- CA-04: Dado um teste falhando na suíte
         Quando o workflow roda
         Então a etapa de testes falha, o workflow é marcado como falho, e build/deploy não executam

- CA-05: Dado o job de testes em execução
         Quando os testes tentam se conectar ao banco
         Então conectam a um PostgreSQL efêmero do próprio Actions, nunca ao banco de staging/produção real

- CA-06: Dado o workflow YAML versionado no repositório
         Quando inspecionado
         Então nenhuma credencial ou segredo aparece em texto puro — todos referenciados via `${{ secrets.NOME }}`

- CA-07: Dado um push em `main` bem-sucedido em lint/teste/build
         Quando a etapa de deploy para produção é alcançada
         Então ela aguarda aprovação manual configurada no GitHub Environment antes de prosseguir

- CA-08: Dado o build da imagem Docker concluído com sucesso
         Quando a etapa de deploy é executada
         Então ela reutiliza a mesma imagem gerada no build, sem reconstruir

---

## Erros e exceções

- Guard A (crítico — propaga): falha em qualquer etapa obrigatória (lint, teste, build) → workflow inteiro marcado como falho, etapas seguintes canceladas, notificação padrão do GitHub Actions ao responsável pelo commit/PR
- Guard B (fallback): nenhum aplicável — pipeline de CI/CD não deve ter fallback silencioso; falha deve ser sempre visível
- Guard C (silencioso): nenhum aplicável pelo mesmo motivo do Guard B

---

## Referência de implementação

**`.github/workflows/ci-cd.yml`:**
```yaml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Instalar Poetry
        run: pipx install poetry
      - name: Instalar dependências
        run: poetry install --no-interaction
      - name: Rodar lint
        run: |
          poetry run ruff check .
          poetry run black --check .

  testes:
    runs-on: ubuntu-latest
    needs: lint
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_DB: lacrei_test
          POSTGRES_USER: postgres
          POSTGRES_PASSWORD: postgres
        ports: ["5432:5432"]
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Instalar Poetry
        run: pipx install poetry
      - name: Instalar dependências
        run: poetry install --no-interaction
      - name: Rodar testes
        env:
          DJANGO_SETTINGS_MODULE: config.settings.development
          SECRET_KEY: chave-de-teste-apenas-para-ci
          # DATABASE_URL é a única variável que o Django lê (ver SDD-01) — os
          # valores abaixo precisam bater com os do service container postgres acima
          DATABASE_URL: postgres://postgres:postgres@localhost:5432/lacrei_test
        run: poetry run python manage.py test

  build:
    runs-on: ubuntu-latest
    needs: testes
    steps:
      - uses: actions/checkout@v4
      - name: Configurar credenciais AWS
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ secrets.AWS_REGION }}
      - name: Login no Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2
      - name: Build e push da imagem
        if: github.event_name == 'push'
        uses: docker/build-push-action@v5
        with:
          context: .
          push: true
          tags: ${{ steps.login-ecr.outputs.registry }}/lacrei-api:${{ github.sha }}
      - name: Build sem push (validação em PR)
        if: github.event_name == 'pull_request'
        uses: docker/build-push-action@v5
        with:
          context: .
          push: false
          tags: lacrei-api:pr-${{ github.event.pull_request.number }}

  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'push'
    environment: staging
    steps:
      - name: Deploy para staging
        run: echo "Deploy da imagem ${{ github.sha }} para staging (detalhado no SDD-07)"

  deploy-producao:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.event_name == 'push'
    environment: producao   # GitHub Environment com required reviewers configurado
    steps:
      - name: Deploy para produção
        run: echo "Deploy da imagem ${{ github.sha }} para produção (detalhado no SDD-07)"
```

**Nota sobre RN-06 (aprovação manual para produção):** implementado via **GitHub Environments** — o environment `producao` é configurado nas settings do repositório com "Required reviewers", pausando o job `deploy-producao` até que um reviewer aprove manualmente. Isso não aparece no YAML em si, é configuração do repositório (documentar no README/SDD-09 como parte do fluxo de deploy).

**Nota sobre alinhamento com o SDD-07 (registry):** o job `build` agora publica no **Amazon ECR** via `aws-actions/amazon-ecr-login`, usando as mesmas credenciais AWS (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`) que o SDD-07 usa no deploy via SSH. O secret `ECR_REGISTRY` referenciado no SDD-07 deve apontar para o mesmo registry/conta AWS resolvido aqui — ambos os SDDs precisam estar configurados na mesma conta/região para a tag `github.sha` ser encontrada no momento do deploy.

**Secrets necessários no repositório GitHub (consolidado — build + deploy):**
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (build, SDD-06, e deploy, SDD-07)
- `ECR_REGISTRY` (deploy — SDD-07)
- `EC2_HOST`, `EC2_USER`, `EC2_SSH_KEY` (deploy — SDD-07)

**Dependências de lint a adicionar no `pyproject.toml` (grupo dev):**
- `ruff`, `black`

---

## Checklist de implementação

- [ ] Workflow dispara em `push` e `pull_request` para `main`
- [ ] Job `testes` usa PostgreSQL como service container, nunca banco real
- [ ] Job `build` roda em **ambos** `push` e `pull_request` (RN-03/CA-02) — só o `push` (com push da imagem) publica no ECR; PR builda sem publicar
- [ ] Login no ECR via `aws-actions/amazon-ecr-login`, consistente com o registry usado no deploy (SDD-07)
- [ ] Nenhum segredo em texto puro no YAML — todos via `secrets.*`
- [ ] `deploy-producao` configurado como GitHub Environment com required reviewers
- [ ] Falha em qualquer etapa cancela as seguintes (comportamento padrão do Actions, sem `continue-on-error`)
- [ ] Imagem buildada uma única vez (no push) e reutilizada no deploy (RN-09)
- [ ] `ruff`/`black` adicionados como dependências de desenvolvimento no Poetry
