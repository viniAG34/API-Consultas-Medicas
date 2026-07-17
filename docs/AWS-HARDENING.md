# Decisão — Hardening AWS: o que foi adotado e o que foi adiado
> ADR de infraestrutura. Referência avaliada: checklist de boas práticas AWS para deploy
> (documento externo fornecido, focado em produção real com tráfego e responsabilidade
> contínua). Este documento registra o que foi adotado dado o prazo do desafio (entrega em
> ~24h da avaliação) e o que foi conscientemente adiado, com justificativa.
> Data: 2026-07-16 — atualizado em 2026-07-17 com achados do provisionamento real.

---

## Correção de contexto antes das decisões

O checklist avaliado assume tratamento de **dado de paciente** (nome, CPF, diagnóstico) para
enquadrar a seção de LGPD como "dado sensível de saúde" (art. 5º, II). O schema real deste
projeto (SDD-02) **não modela paciente nenhum** — apenas `Profissional` (dado do próprio
profissional de saúde) e `Consulta` (FK + horário). Não há CPF, diagnóstico ou nome de
paciente em nenhum lugar do banco. Isso não elimina a responsabilidade sobre dado pessoal do
profissional, mas reduz a urgência de "dado sensível de saúde" que o checklist assume
genericamente — vale essa correção antes de aplicar a seção 9 do documento ao pé da letra.

---

## Adotado agora (custo baixo, alto valor, cabe no prazo)

| Item | Onde | Justificativa |
|---|---|---|
| EBS encryption habilitado | Checkbox na criação do volume EC2 | Zero esforço extra — não implementar seria negligência gratuita |
| Elastic IP (em vez de IP público dinâmico) | Alocado e associado à instância | Evita que o IP mude e quebre o DNS/registro A depois — economiza um problema real, não só teórico |
| Policy do IAM restrita ao ARN do repositório ECR específico | IAM do usuário usado pelo GitHub Actions | Mesmo esforço que escrever `Resource: *` — só precisa saber o ARN antes de escrever o JSON |
| **IAM Role (Instance Profile) na EC2, sem chave estática em disco** | Função `lacrei-api-ecr-pull` anexada à instância | Adotado além do checklist original: a EC2 se autentica no ECR via `sts:assumed-role`, sem nenhuma credencial AWS gravada na máquina — reduz superfície de ataque sem custo de setup adicional (é só uma Role + policy de leitura) |
| Nginx: porta 80 redirecionando para 443 | `nginx/conf.d/*.conf` (SDD-07) | Nginx já seria configurado de qualquer forma — é uma diretiva a mais no mesmo arquivo |
| `mem_limit`/`cpus` no `docker-compose.yml` de cada ambiente | Staging e produção, separadamente | Mitiga diretamente o risco #1 do checklist (staging derrubar produção) sem precisar de uma segunda instância |
| Nomes de projeto Compose distintos (`-p staging`/`-p producao`) | Consequência natural de diretórios separados (`/opt/lacrei/staging/`, `/opt/lacrei/producao/`) já definidos no SDD-07 | Só formalizar como regra explícita, sem custo adicional |
| Swap de 4GB na instância | Bootstrap da EC2 | Poucos comandos de shell, evita o Postgres morrer por OOM Killer em instância pequena |
| Seed sintético em staging, nunca dado real | Prática documentada | Já é o comportamento natural — não existe dado real ainda. Só vira regra formal |

---

## Adiado conscientemente (dívida técnica documentada, não esquecimento)

| Item | Por que foi adiado | Mitigação aceita nesse meio-tempo |
|---|---|---|
| VPC dedicada (em vez da VPC default) | Setup real de rede sob prazo apertado, risco de erro de configuração | VPC default da conta — aceitável para 1 instância, sem tráfego de produção real ainda |
| OIDC entre GitHub Actions e AWS | Requer criar Identity Provider + trust policy + reescrever autenticação do workflow — não é "mais uma linha", é mecanismo novo a validar | Usuário IAM com chave de acesso estática, mas com policy restrita ao ARN específico (ver tabela acima) — reduz o principal risco (permissão excessiva), mantém o risco secundário (chave de longa duração) |
| AWS Systems Manager Session Manager (SSM) | Requer IAM Instance Profile + validar conectividade SSM — aprendizado novo sob pressão | SSH tradicional — ver decisão detalhada abaixo, esta foi revisada durante o provisionamento real |
| Parameter Store / Secrets Manager | Mudança real de arquitetura (app precisaria buscar segredo via SDK no boot, ou integração com Instance Profile) | `.env.staging`/`.env.production` residem só na instância EC2, nunca no Git — já era a decisão do SDD-07, mantida |
| CloudWatch Logs / Agent / alarmes | Já era decisão adiada desde antes deste checklist (ver conversa anterior sobre CloudWatch) — fora do escopo de avaliação backend | `docker logs` local, com os logs já em JSON estruturado (SDD-04) — suficiente para debug manual nesta fase |
| Backup automatizado (snapshot do EBS + `pg_dump` para S3) | Setup de automação (cron + IAM permission pra S3 + bucket com versionamento) | Nenhuma, por ora — risco aceito dado que não há dado real de produção ainda nesta fase de avaliação |
| Blue-green deploy sem downtime | Contradiz a decisão deliberada de simplicidade de uma EC2 só (SDD-07) — Traefik/roteamento dinâmico é complexidade nova | `docker compose up -d --wait` (SDD-07) — poucos segundos de indisponibilidade por deploy, aceitável nesta fase |
| RDS, ALB, WAF, Auto Scaling | Explicitamente fora de escopo — "próximo degrau de maturidade" do próprio checklist avaliado | N/A — decisão já documentada no SDD-07 como trade-off consciente de EC2 única |

---

## Decisão revisada durante o provisionamento real: porta 22 aberta a `0.0.0.0/0`

**O que aconteceu:** a decisão original era restringir SSH (porta 22) ao IP do desenvolvedor
(`My IP` no Security Group). Isso quebrou o job `deploy-staging`/`deploy-producao` do
pipeline: o GitHub Actions executa em runners com **IP dinâmico e imprevisível** — nunca é
"o IP do desenvolvedor" — então a própria automação de deploy ficava bloqueada pela regra
pensada para proteger o acesso manual.

**Decisão tomada:** abrir a porta 22 para `0.0.0.0/0`, mantendo a autenticação por **chave
SSH** (login por senha desabilitado por padrão na AMI Ubuntu) como a barreira real de
segurança — é abrir a porta, não abrir a casa.

**Por que não foi resolvido "direito" (SSM ou IP dinâmico por job) nesta entrega:** as duas
alternativas corretas exigem trabalho real sob o prazo do desafio:
- **SSM Session Manager** elimina a porta 22 por completo, mas exige um IAM Instance Profile
  adicional e validar conectividade — já adiado por esse mesmo motivo na tabela acima.
- **Abrir/fechar a porta dinamicamente por execução do pipeline** (um step no workflow que
  autoriza o IP do runner daquela execução específica via `ec2:AuthorizeSecurityGroupIngress`
  e revoga ao final) é a solução mais correta sem abrir mão de restrição — mas exige
  permissão IAM adicional e dois steps novos no YAML, não implementado nesta entrega.

**Mitigação aceita:** autenticação por chave privada (nunca senha), chave nunca commitada
(vive só como GitHub Secret), e o próximo item da lista de "quando revisitar" abaixo já reflete
essa prioridade.

---

## Bugs reais encontrados durante o provisionamento (ver SDD-07 para detalhe técnico completo)

Durante a primeira subida real dos ambientes, 4 problemas apareceram que nenhuma revisão de
spec/código estático teria pego — só rodando contra infraestrutura de verdade:

1. `DATABASE_URL` precisava ser sintetizada explicitamente via bloco `environment:` no
   `docker-compose.yml` (não bastava `env_file`, já que a chave não existe pronta no `.env`)
2. `--no-deps` no deploy quebrava a primeira subida de cada ambiente (container `db` nunca
   chegava a existir antes do `web` tentar se conectar a ele)
3. `curl` não existe na imagem de runtime enxuta — o healthcheck precisou trocar para
   Python (`urllib`), que sempre está disponível
4. `SECURE_SSL_REDIRECT=True` (adicionado no pente-fino de qualidade) quebrava o healthcheck
   interno do Docker, que fala HTTP puro direto com `localhost` — corrigido com
   `SECURE_REDIRECT_EXEMPT = [r"^health/$"]`

Documentação técnica completa de cada um: `docs/SDD-07-DEPLOY-AWS.md`, seção "Correções
pós-implementação".

---

## Quando revisitar

Se este projeto sair do estágio de desafio de avaliação para uso real e contínuo (ex: a
Lacrei Saúde de fato adotar o serviço em produção com tráfego real), a ordem de prioridade
para destravar os itens adiados seria:

1. **Porta 22 dinâmica por execução do pipeline (ou migrar para SSM)** — mitiga o item mais
   recentemente revisado, e é relativamente barato de implementar (um step de workflow)
2. **Backup automatizado** (proteção contra perda de dado é sempre a mais urgente depois disso)
3. **OIDC** (redução de superfície de ataque da automação)
4. **Parameter Store**
5. O restante por ordem do próprio checklist original ("próximo degrau de maturidade")
