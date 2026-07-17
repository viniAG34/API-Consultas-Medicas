# SDD-07 — Deploy AWS (Staging e Produção)
> Leia SDD-01 e SDD-06 antes de implementar.
> Última atualização: 2026-07-09

---

## Responsabilidade

Definir a infraestrutura de deploy na AWS para os ambientes de staging e produção, o fluxo de publicação de imagem via ECR, e a estratégia de rollback funcional.

**Não faz:** não define o pipeline de CI/CD em si (SDD-06 já cobre as etapas até o disparo do deploy). Define exclusivamente onde e como a aplicação roda depois de deployada.

---

## Decisão de arquitetura (justificativa técnica)

Dado o prazo do desafio (5 dias úteis) e o escopo de uma API de CRUD sem carga de produção real, optou-se por **uma única instância EC2** hospedando os dois ambientes (staging e produção) via Docker Compose, em vez de ECS/Fargate ou Elastic Beanstalk. Essa escolha prioriza:
- Reutilização direta do `docker-compose.yml` já validado no SDD-01, sem reescrever para orquestração gerenciada
- Menor superfície de configuração nova a aprender/depurar sob prazo apertado
- Ainda assim atende ao critério obrigatório de "ambientes separados: staging e produção" — a separação é lógica (containers, portas e domínios distintos), não física por instância

**Trade-off documentado (para o README/SDD-09):** em um cenário de produção real, staging e produção rodariam em instâncias/contas AWS separadas, e o banco usaria RDS gerenciado em vez de container Postgres na própria instância. Essa simplificação é uma decisão consciente de escopo para o desafio, não uma limitação técnica desconhecida.

---

## Regras de negócio

- RN-01: Staging e produção rodam como stacks Docker Compose independentes na mesma instância EC2, cada uma com seu próprio arquivo `.env` (um por diretório — `staging/.env` e `producao/.env`) — nenhuma variável de ambiente é compartilhada entre os dois; o isolamento é garantido pela separação de diretórios, não pelo nome do arquivo.
- RN-02: Cada ambiente tem seu próprio banco PostgreSQL (containers separados, volumes separados) — dados de staging nunca se misturam com produção.
- RN-03: O acesso a cada ambiente é feito por subdomínio distinto (ex: `staging.api-lacrei.<dominio>` e `api-lacrei.<dominio>`), roteado por Nginx como reverse proxy na própria instância.
- RN-04: A imagem Docker publicada pelo CI/CD (SDD-06) é armazenada no **Amazon ECR**, versionada pela tag do commit (`github.sha`) — nunca `latest` como única tag.
- RN-05: O deploy consiste em: puxar a nova imagem do ECR na instância, atualizar o `docker-compose` do ambiente alvo para apontar para a nova tag, e recriar apenas o container da aplicação (não recria o banco).
- RN-06: `migrate` roda automaticamente como parte do entrypoint do container (RN-12 do SDD-01) — não é um passo manual separado no deploy.
- RN-07: O rollback consiste em reapontar o `docker-compose` do ambiente para a tag de imagem anterior (já publicada no ECR) e recriar o container — nunca depende de rebuild.
- RN-08: Toda credencial de acesso à instância EC2 (chave SSH) e à conta AWS (chaves de acesso do ECR) fica em GitHub Secrets, nunca no repositório.
- RN-09: O Security Group da instância EC2 libera apenas as portas necessárias (22 para SSH restrito a IP conhecido, 80/443 para HTTP/HTTPS) — nenhuma porta de banco exposta publicamente.
- RN-10: HTTPS é obrigatório em ambos os ambientes — certificado via Let's Encrypt (Certbot) integrado ao Nginx.

---

## Critérios de aceite

- CA-01: Dado o domínio de produção configurado
         Quando acessado via HTTPS
         Então a API responde corretamente com certificado válido (sem aviso de segurança no navegador)

- CA-02: Dado o domínio de staging configurado
         Quando acessado via HTTPS
         Então a API responde corretamente, de forma independente da instância de produção

- CA-03: Dado um novo deploy disparado pelo pipeline (SDD-06) para staging
         Quando o processo é concluído
         Então a nova versão está ativa em staging sem afetar o container de produção

- CA-04: Dado um dado criado em staging
         Quando consultado o banco de produção
         Então o dado não existe lá — bancos completamente isolados

- CA-05: Dado um deploy que introduziu um problema em produção
         Quando o comando de rollback é executado (manual ou via workflow)
         Então a aplicação volta a rodar a imagem da tag anterior em menos de alguns minutos, sem necessidade de rebuild

- CA-06: Dado o Security Group da instância EC2
         Quando inspecionado
         Então a porta do PostgreSQL (5432) não está aberta para `0.0.0.0/0`

- CA-07: Dado o endpoint `/health/` (SDD-01)
         Quando acessado em produção após um deploy
         Então retorna `200`, confirmando que o container subiu e está conectado ao banco antes do tráfego ser considerado saudável

- CA-08: Dado o processo de deploy
         Quando executado
         Então utiliza a mesma imagem buildada no CI (SDD-06, RN-09) — nunca builda a imagem diretamente na instância EC2

---

## Erros e exceções

- Guard A (crítico — propaga): falha ao subir o novo container (ex: erro de migration, crash no boot) → deploy é considerado falho, o container anterior permanece rodando (Docker Compose não remove o container antigo até o novo confirmar saúde), alertando a necessidade de rollback manual se o healthcheck não passar
- Guard B (fallback): falha ao obter certificado renovado do Let's Encrypt → Nginx continua servindo com o certificado anterior até a próxima tentativa de renovação (Certbot já possui esse comportamento nativo)
- Guard C (silencioso): log de deploy (sucesso/falha, tag de imagem, timestamp) sempre registrado na instância, sem interromper o fluxo caso o log falhe

---

## Referência de implementação

**Estrutura na instância EC2:**
```
/opt/lacrei/
├── staging/
│   ├── docker-compose.yml
│   └── .env
├── producao/
│   ├── docker-compose.yml
│   └── .env
└── nginx/
    └── conf.d/
        ├── staging.conf
        └── producao.conf
```

**`docker-compose.yml` (por ambiente — exemplo produção):**
```yaml
services:
  web:
    image: ${ECR_REGISTRY}/lacrei-api:${IMAGE_TAG}
    env_file: .env.production
    restart: always
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health/"]
      interval: 30s
      timeout: 5s
      retries: 3
    expose:
      - "8000"

  db:
    image: postgres:16
    env_file: .env.production
    restart: always
    volumes:
      - postgres_data_producao:/var/lib/postgresql/data

volumes:
  postgres_data_producao:
```

**`nginx/conf.d/producao.conf`:**
```nginx
server {
    listen 443 ssl;
    server_name api-lacrei.<dominio>;

    ssl_certificate     /etc/letsencrypt/live/api-lacrei.<dominio>/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api-lacrei.<dominio>/privkey.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

**Etapa de deploy no `.github/workflows/ci-cd.yml` (substituindo o placeholder do SDD-06):**
```yaml
  deploy-staging:
    runs-on: ubuntu-latest
    needs: build
    if: github.event_name == 'push'
    environment: staging
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /opt/lacrei/staging
            export IMAGE_TAG=${{ github.sha }}
            export ECR_REGISTRY=${{ secrets.ECR_REGISTRY }}
            aws ecr get-login-password --region ${{ secrets.AWS_REGION }} | docker login --username AWS --password-stdin $ECR_REGISTRY
            docker compose pull web
            docker compose up -d --no-deps web
            curl -f http://localhost:8000/health/ || (echo "Healthcheck falhou" && exit 1)

  deploy-producao:
    runs-on: ubuntu-latest
    needs: deploy-staging
    if: github.event_name == 'push'
    environment: producao   # required reviewers configurado (SDD-06)
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.EC2_HOST }}
          username: ${{ secrets.EC2_USER }}
          key: ${{ secrets.EC2_SSH_KEY }}
          script: |
            cd /opt/lacrei/producao
            export IMAGE_TAG=${{ github.sha }}
            export ECR_REGISTRY=${{ secrets.ECR_REGISTRY }}
            aws ecr get-login-password --region ${{ secrets.AWS_REGION }} | docker login --username AWS --password-stdin $ECR_REGISTRY
            docker compose pull web
            docker compose up -d --no-deps web
            curl -f http://localhost:8000/health/ || (echo "Healthcheck falhou" && exit 1)
```

**Rollback (RN-07) — comando manual ou workflow dedicado:**
```bash
# Na instância, dentro da pasta do ambiente (ex: /opt/lacrei/producao)
export ECR_REGISTRY=<valor do secret ECR_REGISTRY>
export IMAGE_TAG=<sha-da-versao-anterior-conhecida-boa>
docker compose pull web
docker compose up -d --wait --wait-timeout 60
```

Pode ser formalizado como `workflow_dispatch` manual no GitHub Actions recebendo `IMAGE_TAG` como input, reaproveitando os mesmos steps de SSH — documentar essa opção no SDD-09 como "rollback via GitHub Actions" (uma das formas sugeridas pelo próprio PDF do desafio).

---

## Correções pós-implementação

> Mesmo padrão de registro usado no SDD-03 para o `UniqueTogetherValidator` (bug real
> encontrado, causa raiz documentada, correção aplicada). Os 4 itens abaixo foram
> encontrados durante o provisionamento manual da instância EC2 (via SSH direto, fora do
> Claude Code) e só foram sincronizados de volta para o repositório depois — as referências
> reais ficam em `deploy/staging/docker-compose.yml`, `deploy/producao/docker-compose.yml` e
> `deploy/nginx/conf.d/`.

**1. `DATABASE_URL` precisa ser sintetizada via bloco `environment:`, não só `env_file`.**
Causa raiz: o Docker Compose lê automaticamente um arquivo `.env` no mesmo diretório do
`docker-compose.yml` para resolver `${VAR}` usado dentro do próprio YAML (ex:
`${POSTGRES_USER}` no serviço `db`) — isso é diferente de `env_file:`, que só injeta
variáveis *dentro* do container. O `.env` de cada ambiente (`/opt/lacrei/staging/.env` e
`/opt/lacrei/producao/.env`) só tem as chaves `POSTGRES_*`, nunca `DATABASE_URL`. Sem a
síntese explícita, o container `web` sobe sem `DATABASE_URL` no ambiente e o Django falha ao
conectar. Correção — replicada nas duas referências em `deploy/`:
```yaml
environment:
  DATABASE_URL: postgres://${POSTGRES_USER}:${POSTGRES_PASSWORD}@db:${POSTGRES_PORT}/${POSTGRES_DB}
```
**Nota de nomenclatura:** por causa dessa mesma exigência do Compose (o arquivo de
interpolação de YAML precisa se chamar literalmente `.env`), os arquivos reais na instância
são `.env` dentro de cada diretório (`staging/`, `producao/`), não `.env.staging`/
`.env.production` como o exemplo original deste SDD sugeria — o isolamento entre ambientes
(RN-01) continua garantido porque cada um vive no seu próprio diretório.

**2. `--no-deps` no deploy quebra a primeira subida de um ambiente novo.**
Causa raiz: se o container `db` ainda não existe (primeiro deploy do ambiente), `docker
compose up -d --no-deps web` sobe **só** o `web`, que não consegue resolver o hostname `db`
— a rede do Compose nem tem o serviço `db` para apontar. Correção, já aplicada em
`.github/workflows/ci-cd.yml` (`deploy-staging`/`deploy-producao`): trocado para `docker
compose up -d --wait --wait-timeout 60`, sem `--no-deps` e sem `web` no final — sobe/atualiza
todos os serviços que precisarem, e só considera o deploy bem-sucedido quando o healthcheck
confirmar saúde.

**3. `curl` não existe na imagem de runtime.**
Causa raiz: o estágio final do `Dockerfile` (`python:3.12-slim`, sem ferramentas de build) não
inclui `curl` — então um `healthcheck` de `docker-compose.yml` baseado em `curl -f
http://localhost:8000/health/` falha sempre, mesmo com a aplicação saudável. Python, por outro
lado, sempre existe na imagem. Correção, aplicada nas referências em `deploy/`:
```yaml
healthcheck:
  test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/')"]
  interval: 5s
  timeout: 5s
  retries: 5
  start_period: 15s
```

**4. `SECURE_SSL_REDIRECT=True` quebra o healthcheck interno.**
Causa raiz: o healthcheck do Compose fala `http://localhost:8000/health/` de dentro do
próprio container — nunca passa pelo Nginx, então nunca carrega o cabeçalho
`X-Forwarded-Proto: https` que `SECURE_PROXY_SSL_HEADER` espera. Com `SECURE_SSL_REDIRECT`
ativo, essa requisição HTTP interna é tratada como insegura e o Django tenta redirecioná-la,
quebrando o healthcheck. Correção, em `config/settings/production.py`:
```python
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
```
Confirmado que já está no repositório (linha 16 de `config/settings/production.py`, commitado
e deployado antes desta sessão) — nenhuma ação adicional necessária.

**5. Achado adicional, menor: `ALLOWED_HOSTS` precisa incluir `localhost,127.0.0.1`.**
Causa raiz: o cabeçalho `Host` da requisição interna do healthcheck (feita de dentro do
próprio container, para `localhost:8000`) é sempre `localhost`, nunca o domínio público — sem
`localhost`/`127.0.0.1` em `ALLOWED_HOSTS`, o Django rejeita com 400 (`DisallowedHost`) antes
mesmo de chegar à view. Resolvido no `.env` real da instância; documentado como nota em
`.env.example` para não repetir o problema em ambientes futuros.

**6. Rollback (RN-07) testado com uso real, não só descrito na spec.**
Testado revertendo staging para uma imagem anterior à correção do item 4
(`SECURE_REDIRECT_EXEMPT`) — reproduziu o `unhealthy` esperado, confirmando que o
healthcheck detecta regressão real. Em seguida, testado retornando à imagem corrigida
(`f42ab02`) — confirmou `healthy` em ~24s, sem intervenção manual além do comando em si.
Conclusão: mecanismo de rollback validado com uso real, atende RN-07 e ao item do checklist
"procedimento de rollback testado manualmente ao menos uma vez antes da entrega".

---

## Checklist de implementação

- [ ] Repositório ECR criado para `lacrei-api`
- [ ] Instância EC2 provisionada com Docker e Docker Compose instalados
- [ ] Security Group liberando apenas 22 (IP restrito), 80 e 443
- [ ] `.env` criado diretamente na instância, um por diretório (`staging/`, `producao/`) (nunca versionados)
- [ ] Nginx configurado com dois `server blocks`, um por ambiente/subdomínio
- [ ] Certbot configurado para emissão e renovação automática de certificado em ambos os domínios
- [ ] Bancos de staging e produção em volumes Docker separados
- [ ] Deploy usa tag de imagem específica (`github.sha`), nunca `latest`
- [ ] Healthcheck (`/health/`) validado após cada deploy antes de considerar sucesso
- [x] Procedimento de rollback testado manualmente ao menos uma vez antes da entrega
