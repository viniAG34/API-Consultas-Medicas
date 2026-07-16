# Boas Práticas AWS — Deploy da API de Consultas Médicas (Lacrei Saúde)

> Contexto avaliado: EC2 única rodando staging + produção via Docker Compose, ECR para imagens, IAM restrito ao GitHub Actions, Security Group liberando 22/80/443.
> Este documento assume um projeto **early-stage, custo-sensível, mas que lida com dados de saúde** (LGPD aplicável). As recomendações são organizadas por criticidade: 🔴 Crítico (fazer antes de subir), 🟡 Importante (fazer nas próximas semanas), 🟢 Nice-to-have (quando o produto crescer).

---

## 0. Risco arquitetural principal: Staging + Produção na mesma EC2

🔴 **Crítico**

Isso é o ponto mais frágil do desenho atual. Os riscos concretos:

| Risco | Impacto |
|---|---|
| Container de staging consome CPU/RAM em excesso | Derruba ou degrada produção na mesma máquina |
| Mesma Security Group / IAM Role / rede | Uma vulnerabilidade em staging expõe produção |
| Mesmo disco (EBS) | Log verboso ou build de staging enche disco e derruba prod |
| Deploy de staging com erro humano | Risco de rodar `docker compose down` no ambiente errado |
| Dados de saúde (LGPD) | Se staging usa dump de dados reais de pacientes, você tem PII exposta num ambiente com padrão de segurança mais frouxo |

**Mitigação de baixo custo (sem dobrar a EC2):**

- **Nunca usar dados reais em staging.** Seed sintético/anonimizado sempre. Isso sozinho já reduz o risco de LGPD de "grave" para "baixo".
- Isolar staging e produção em **containers com limites de recursos explícitos** (`mem_limit`, `cpus` no Docker Compose), para que staging nunca consuma além de uma fatia fixa.
- Colocar staging e produção em **redes Docker (bridge) separadas**, cada uma com seu próprio Postgres/Redis em container isolado — nunca compartilhar banco.
- Usar **volumes e nomes de projeto Compose distintos** (`docker compose -p staging` vs `-p prod`) para eliminar erro humano de comando no ambiente errado.
- Se o orçamento permitir mais adiante: mover staging para uma **instância `t3.micro`/`t4g.micro` separada** (pode custar ~US$ 6-8/mês a mais, ou até free tier dependendo da conta) — é o upgrade de segurança com melhor custo-benefício que existe aqui.

Se o objetivo é "subir logo e crescer depois", tudo bem manter uma EC2 só por enquanto — mas trate isso como **dívida técnica documentada**, não como decisão definitiva.

---

## 1. Rede (VPC / Subnets)

🔴 Crítico | 🟡 Importante conforme indicado

- 🔴 Não use a **VPC default** da conta para produção. Crie uma VPC dedicada, mesmo que pequena (`10.0.0.0/16`).
- 🔴 A EC2 deve ficar em uma **subnet pública** apenas porque precisa de IP público para servir HTTP/HTTPS diretamente (sem ALB). Isso é aceitável nesse estágio, mas:
  - Desative **auto-assign public IP** e use um **Elastic IP** fixo — evita que o IP mude a cada restart/parada da instância (o que quebraria DNS/registros A).
  - Considere criar já a subnet privada, mesmo vazia, para o dia em que o banco de dados sair do container e for para RDS (nunca exponha banco de dados em subnet pública).
- 🟡 Route Table: mantenha explícita, revise que não há rota `0.0.0.0/0` desnecessária além do Internet Gateway.
- 🟢 NAT Gateway só se/quando existir algo em subnet privada precisando sair para a internet (ex: worker fazendo chamada a API externa). Não crie agora — tem custo fixo (~US$ 32/mês) sem uso hoje.

---

## 2. IAM

🔴 Crítico

O ponto "só um usuário/chave para o GitHub Actions" precisa de ajuste — **usuário IAM com chave de acesso estática é o padrão mais desatualizado e arriscado que existe hoje para CI/CD.**

### Problema
Chaves de acesso (`AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`) armazenadas como GitHub Secret:
- Não expiram automaticamente.
- Se vazarem (log mal configurado, dependência comprometida, secret exposto em fork de PR), o atacante tem acesso até você revogar manualmente.
- Não há como restringir "só esse pipeline específico pode usar".

### Solução recomendada: **OIDC (OpenID Connect) entre GitHub Actions e AWS**
- Elimina completamente a necessidade de chave de acesso de longa duração.
- O GitHub Actions assume uma **IAM Role temporária** via `sts:AssumeRoleWithWebIdentity`, com credenciais que expiram em minutos.
- Configuração: criar um **IAM Identity Provider** apontando para `token.actions.githubusercontent.com`, e uma Role com **trust policy condicionada ao repositório específico** (`repo:viniAG34/API-Consultas-Medicas:*`).

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:viniAG34/API-Consultas-Medicas:*"
        }
      }
    }
  ]
}
```

No workflow do GitHub Actions:
```yaml
permissions:
  id-token: write
  contents: read

steps:
  - uses: aws-actions/configure-aws-credentials@v4
    with:
      role-to-assume: arn:aws:iam::<ACCOUNT_ID>:role/github-actions-ecr-deploy
      aws-region: sa-east-1
```

Se por algum motivo OIDC não for viável agora, pelo menos:
- 🔴 Rotacione a chave de acesso a cada 90 dias (automatize um lembrete).
- 🔴 A policy do usuário deve ser **restrita ao ARN do repositório ECR específico**, nunca `ecr:*` em `Resource: *`. Exemplo de policy mínima:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ecr:GetDownloadUrlForLayer",
        "ecr:BatchGetImage",
        "ecr:BatchCheckLayerAvailability",
        "ecr:PutImage",
        "ecr:InitiateLayerUpload",
        "ecr:UploadLayerPart",
        "ecr:CompleteLayerUpload"
      ],
      "Resource": "arn:aws:ecr:sa-east-1:<ACCOUNT_ID>:repository/api-consultas-medicas"
    },
    {
      "Effect": "Allow",
      "Action": "ecr:GetAuthorizationToken",
      "Resource": "*"
    }
  ]
}
```
(`GetAuthorizationToken` exige `Resource: *` — é uma limitação da API do ECR, não uma folga sua.)

### Instância EC2: nunca coloque credenciais AWS dentro dela
- Se a EC2 precisar falar com outros serviços AWS (ex: puxar imagem do ECR no `docker pull`, escrever logs no CloudWatch), use um **IAM Instance Profile / Role** anexado à instância — nunca `aws configure` com chave estática dentro da máquina.

---

## 3. Security Group

🔴 Crítico | ajustes ao que já foi definido

Seu desenho (22 restrito ao seu IP, 80, 443) é o básico correto. Reforços:

- 🔴 **Porta 22 nunca deve ficar aberta 24/7**, mesmo restrita a um IP fixo — IP residencial muda (trocou de rede, 4G, café). Alternativas melhores:
  - **AWS Systems Manager Session Manager (SSM)**: acesso SSH sem abrir porta 22 nenhuma, sem gerenciar chave, com log de auditoria de cada sessão no CloudTrail. É gratuito e é hoje o padrão de mercado para instâncias únicas. Requer o IAM Instance Profile ter a policy `AmazonSSMManagedInstanceCore`.
  - Se preferir manter SSH tradicional: pelo menos use **security group referenciando um Prefix List gerenciada** ou automatize a atualização do IP via script, porque "restrito ao seu IP" quebra silenciosamente e você só descobre quando precisa entrar.
- 🔴 Porta 80 deve **redirecionar para 443**, nunca servir conteúdo em texto plano (configurar isso no Nginx/Traefik, não no Security Group).
- 🟡 Não abra range de portas "por via das dúvidas". Se cada serviço (staging/prod) usa portas internas diferentes, isso deve ficar **atrás do Nginx/Traefik na 443**, nunca exposto direto no Security Group.
- 🟢 Considere **AWS WAF** na frente (via CloudFront ou ALB) quando o tráfego justificar — protege contra SQL injection, XSS e rate limiting a nível de borda, antes mesmo de chegar na EC2.

---

## 4. EC2 — hardening e operação

🔴 / 🟡

- 🔴 **AMI**: use Ubuntu LTS ou Amazon Linux 2023, sempre a versão mais recente do momento do deploy — não uma AMI antiga "porque já testou".
- 🔴 **Tamanho e tipo**: para staging+prod juntos, `t3.small` ou `t4g.small` (ARM, mais barato) costuma ser o mínimo realista para Django + Postgres + Redis em containers, mas monitore memória desde o dia 1 — é o primeiro gargalo em instância pequena com múltiplos containers.
- 🔴 **Swap**: em instância pequena, configure um arquivo de swap (2-4GB) para evitar OOM Killer matando o container do banco no meio da noite.
- 🔴 **Backup do EBS**: ative **snapshots automáticos via AWS Backup** ou um `lifecycle policy` de snapshot diário. Sem isso, uma corrupção de disco (você já teve problema de vhdx corrompido no WSL2 — o mesmo tipo de dor de cabeça pode acontecer aqui) significa perda total de dados.
- 🔴 **Banco de dados fora do "só container"**: mesmo rodando Postgres em container agora, tenha um `pg_dump` automatizado (cron) para um bucket **S3 com versionamento e criptografia (SSE-S3 ou SSE-KMS)**, independente do snapshot de disco. Regra de ouro: **backup de disco protege contra falha de infra; backup lógico (dump) protege contra erro humano** (`DROP TABLE` acidental, migration destrutiva). Você precisa dos dois.
- 🟡 **Migração futura para RDS**: quando o projeto crescer, o primeiro serviço a sair do "tudo na mesma EC2" deveria ser o Postgres → RDS (Multi-AZ), não a aplicação. Motivo: banco de dados é o componente com maior custo de downtime e recovery manual.
- 🟡 **User Data / bootstrap**: documente ou automatize (Ansible/script) a criação da instância do zero. Se a EC2 morrer, você precisa recriar em minutos, não reconstruir na mão lembrando o que instalou há 3 meses.
- 🟢 **Auto Scaling futuro**: não é prioridade agora com 1 instância, mas desenhe o Docker Compose de um jeito que migrar para ECS Fargate no futuro não exija reescrever tudo (mantenha configuração via variáveis de ambiente, sem hardcode de paths locais).

---

## 5. Segredos e configuração

🔴 Crítico

- 🔴 Nunca commit de `.env` no repositório, nem em `docker-compose.yml`. Use **AWS Systems Manager Parameter Store** (gratuito, com criptografia via KMS) ou **AWS Secrets Manager** (pago, mas com rotação automática) para: `SECRET_KEY` do Django, credenciais do Postgres, JWT signing key, credenciais de terceiros.
- 🔴 No pipeline de deploy, os secrets são buscados no momento do `docker compose up`, nunca ficam em disco em texto plano além do necessário.
- 🟡 Separe `.env` de staging e produção com **prefixos diferentes** no Parameter Store (`/prod/api-consultas/DB_PASSWORD` vs `/staging/api-consultas/DB_PASSWORD`), reduzindo o risco de vazamento cruzado.

---

## 6. TLS / Certificados

🔴 Crítico

- 🔴 Use **Let's Encrypt via Traefik ou Certbot+Nginx** para HTTPS gratuito com renovação automática. Para um projeto desse porte, não há motivo para pagar por certificado.
- 🔴 Force **TLS 1.2+ apenas**, desative TLS 1.0/1.1 e cifras fracas na configuração do Nginx/Traefik.
- 🟡 HSTS habilitado (`Strict-Transport-Security`) depois que a renovação automática estiver validada e estável.

---

## 7. Observabilidade

🟡 Importante (pode ser incremental)

- 🟡 **Logs centralizados**: no mínimo, `docker logs` com `json-file` driver e rotação configurada (`max-size`, `max-file`) para não encher o disco. Nível seguinte: enviar para **CloudWatch Logs** via `awslogs` driver do Docker — já vem de graça com o IAM Instance Profile certo.
- 🟡 **Métricas básicas**: **CloudWatch Agent** na EC2 para memória e disco (CloudWatch nativo só cobre CPU/rede por padrão, não memória/disco de dentro da instância).
- 🟡 **Alarme de CloudWatch**: CPU > 80% por 5 min, disco > 85%, status check failed → notificação via **SNS para seu e-mail/WhatsApp**. Isso é barato e evita descobrir problema de produção pelo usuário reclamando.
- 🟢 Quando o produto crescer: Prometheus + Grafana (self-hosted, você já tem familiaridade) ou Grafana Cloud free tier, para métricas de aplicação (latência por endpoint, taxa de erro).

---

## 8. Deploy / CI-CD

🟡 Importante

- 🟡 **Zero-downtime deploy**: mesmo em uma EC2 única, é possível fazer deploy sem downtime com Traefik/Nginx fazendo `blue-green` local — sobe o container novo, healthcheck passa, troca o roteamento, derruba o antigo. Evita o "docker compose down && up" que gera 10-30s de indisponibilidade a cada deploy.
- 🟡 **Healthcheck no Docker Compose**: cada serviço (API, banco, redis) com `healthcheck` definido, para o orquestrador (mesmo que seja só Compose) saber se o container está de fato saudável, não só "rodando".
- 🟡 **Rollback rápido**: tag de imagem no ECR sempre com o SHA do commit (nunca só `latest`), permitindo reverter para a imagem anterior em segundos se o deploy quebrar algo.
- 🟢 **Migrations do Django**: rode como um step separado e explícito no pipeline (`python manage.py migrate --check` antes, depois `migrate` real), nunca dentro do entrypoint do container sem controle — migration destrutiva rodando sem revisão é uma das causas mais comuns de incidente em produção.

---

## 9. LGPD (específico por lidar com dados de saúde)

🔴 Crítico — este projeto tem responsabilidade acima da média

- 🔴 Dados de pacientes são **dados sensíveis** pela LGPD (art. 5º, II) — tratamento exige base legal específica e medidas de segurança reforçadas (art. 46).
- 🔴 Criptografia em trânsito (TLS, já coberto acima) **e em repouso**: habilite **EBS encryption** (é um checkbox na criação do volume, sem custo adicional de performance relevante) e, se usar S3 para backups, **SSE-S3/SSE-KMS**.
- 🔴 Logs de aplicação **nunca devem conter dados de paciente em texto claro** (nome completo, CPF, diagnóstico) — mascare ou omita esses campos no logging estruturado.
- 🟡 Defina e documente política de retenção de backups (ex: 90 dias) — reter para sempre também é um risco de compliance, não só falta de retenção.

---

## Checklist resumido antes de ir ao ar

- [ ] VPC dedicada, subnet pública com Elastic IP
- [ ] Volume EBS com encryption habilitado
- [ ] IAM: OIDC para GitHub Actions (ou, no mínimo, policy restrita por ARN + rotação)
- [ ] Instance Profile na EC2 com `AmazonSSMManagedInstanceCore` (acesso via SSM, não porta 22 aberta)
- [ ] Security Group: 80→443 redirect, 443 aberto, 22 fechado ou via SSM
- [ ] Secrets no Parameter Store / Secrets Manager, nunca em `.env` versionado
- [ ] TLS via Let's Encrypt automatizado
- [ ] Backup de disco (snapshot) + backup lógico (`pg_dump` para S3 com versionamento)
- [ ] Staging isolado (rede/limites de recurso Docker) e com dados sintéticos, nunca reais
- [ ] CloudWatch Agent + alarmes básicos (CPU, disco, status check)
- [ ] Deploy com tags de imagem por SHA (rollback possível)
- [ ] Logs sem PII em texto claro

---

## Próximo degrau de maturidade (quando o orçamento/tráfego crescer)

1. Separar staging em instância própria (`t3.micro`/`t4g.micro`).
2. Migrar Postgres de container para **RDS** (Multi-AZ quando o SLA exigir).
3. Introduzir **ALB** na frente da EC2 (ou migrar para ECS Fargate) para permitir múltiplas instâncias e remover single point of failure de compute.
4. **AWS WAF** + CloudFront na borda.
5. Observabilidade completa (tracing distribuído com OpenTelemetry, já que você tem familiaridade).
