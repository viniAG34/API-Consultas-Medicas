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

- RN-01: Staging e produção rodam como stacks Docker Compose independentes na mesma instância EC2, com arquivos `.env.staging` e `.env.production` distintos — nenhuma variável de ambiente é compartilhada entre os dois.
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
│   └── .env.staging
├── producao/
│   ├── docker-compose.yml
│   └── .env.production
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
export IMAGE_TAG=<sha-da-versao-anterior-conhecida-boa>
docker compose pull web
docker compose up -d --no-deps web
curl -f http://localhost:8000/health/
```

Pode ser formalizado como `workflow_dispatch` manual no GitHub Actions recebendo `IMAGE_TAG` como input, reaproveitando os mesmos steps de SSH — documentar essa opção no SDD-09 como "rollback via GitHub Actions" (uma das formas sugeridas pelo próprio PDF do desafio).

---

## Checklist de implementação

- [ ] Repositório ECR criado para `lacrei-api`
- [ ] Instância EC2 provisionada com Docker e Docker Compose instalados
- [ ] Security Group liberando apenas 22 (IP restrito), 80 e 443
- [ ] `.env.staging` e `.env.production` criados diretamente na instância (nunca versionados)
- [ ] Nginx configurado com dois `server blocks`, um por ambiente/subdomínio
- [ ] Certbot configurado para emissão e renovação automática de certificado em ambos os domínios
- [ ] Bancos de staging e produção em volumes Docker separados
- [ ] Deploy usa tag de imagem específica (`github.sha`), nunca `latest`
- [ ] Healthcheck (`/health/`) validado após cada deploy antes de considerar sucesso
- [ ] Procedimento de rollback testado manualmente ao menos uma vez antes da entrega
