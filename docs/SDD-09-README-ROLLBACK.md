# SDD-09 — README, Decisões Técnicas e Rollback
> Leia todos os SDDs anteriores (01 a 08) antes de implementar — este é o documento de síntese final.
> Última atualização: 2026-07-09

---

## Responsabilidade

Consolidar em um único `README.md` tudo que foi decidido e implementado nos SDDs anteriores, em formato legível para quem for avaliar o projeto: setup local, setup Docker, execução de testes, fluxo de deploy/CI-CD, justificativas técnicas, proposta de rollback, limitações conhecidas e transparência sobre o uso de metodologia SDD com IA.

**Não faz:** não implementa nenhuma funcionalidade nova. É o documento final que amarra a narrativa de todos os SDDs anteriores para quem lê o repositório de fora.

---

## Regras de negócio

- RN-01: O README é o primeiro arquivo que um avaliador vê — precisa permitir rodar o projeto localmente (Docker) sem precisar ler nenhum outro documento.
- RN-02: Toda decisão técnica não óbvia (ex: `on_delete=PROTECT`, instância EC2 única para staging+produção, autenticação também em GET) é justificada explicitamente — decisão sem justificativa é tratada como pendência.
- RN-03: O README declara transparentemente o uso de metodologia SDD com apoio de Claude Code no desenvolvimento, linkando para `docs/specs/`, conforme decidido anteriormente nesta conversa.
- RN-04: Limitações conscientes de escopo (CloudWatch não implementado, staging/produção na mesma instância, processamento assíncrono não implementado) são documentadas como **decisão consciente por prazo**, não omitidas nem apresentadas como desconhecimento.
- RN-05: A proposta de rollback documentada é a mesma implementada de fato no SDD-07 (retag de imagem ECR) — o README nunca descreve um rollback teórico diferente do que foi implementado.
- RN-06: O README inclui a matriz de rastreabilidade de alto nível (SDD → funcionalidade), permitindo ao avaliador navegar da tabela de critérios do desafio direto para o SDD correspondente.
- RN-07: Comandos no README são copiáveis e testados — nenhum comando de exemplo com placeholder não explicado (ex: `<seu-token>` sem dizer onde obtê-lo).

---

## Critérios de aceite

- CA-01: Dado o README
         Quando um avaliador segue a seção "Setup com Docker" do zero (`git clone` + comandos)
         Então a API sobe localmente e responde em `/health/` sem nenhum passo omitido

- CA-02: Dado o README
         Quando inspecionada a seção de testes
         Então contém o comando exato para rodar a suíte completa e para rodar por categoria (unitário, integração, regressão, contrato — conforme SDD-05)

- CA-03: Dado o README
         Quando inspecionada a seção de decisões técnicas
         Então cada decisão relevante (ver RN-02) tem uma frase de justificativa, não apenas a decisão enunciada

- CA-04: Dado o README
         Quando inspecionada a seção de rollback
         Então descreve o comando/fluxo real usado (SDD-07, RN-07), incluindo a opção via GitHub Actions `workflow_dispatch`

- CA-05: Dado o README
         Quando inspecionada a seção sobre metodologia
         Então menciona o uso de SDD com apoio de Claude Code, sem overclaim nem omissão, e linka para `docs/specs/`

- CA-06: Dado o README
         Quando inspecionada a seção de limitações conhecidas
         Então lista CloudWatch, instância única EC2, e processamento assíncrono como decisões conscientes de escopo — não como bugs ou esquecimentos

- CA-07: Dado o README
         Quando comparado com a tabela de critérios de aceite do PDF do desafio
         Então todo item obrigatório tem uma seção ou referência correspondente visível

---

## Erros e exceções

- Guard A (crítico — propaga): comando documentado no README que não funciona de fato → tratado como bug de documentação, deve ser corrigido antes da entrega (validar cada comando manualmente antes do envio)
- Guard B (fallback): nenhum aplicável — documentação não tem fallback, ou está correta ou está incompleta
- Guard C (silencioso): nenhum aplicável pelo mesmo motivo

---

## Referência de implementação

**Estrutura sugerida do `README.md`:**

```markdown
# API de Gerenciamento de Consultas Médicas — Lacrei Saúde

[Badge de build do GitHub Actions]

## Sobre o projeto
[1 parágrafo: contexto do desafio, propósito social]

## Stack
[Tabela reaproveitada da seção 8 do CLAUDE.md]

## Setup local (sem Docker)
[Comandos Poetry — SDD-01]

## Setup com Docker
[Comandos docker-compose — SDD-01]

## Variáveis de ambiente
[Tabela do .env.example]

## Endpoints
[Link para /api/docs/ (SDD-08) + lista resumida dos principais endpoints]

## Autenticação
[Como obter token, exemplo de curl — SDD-04]

## Executando os testes
[Comandos por categoria — SDD-05]
- Todos: `python manage.py test`
- Apenas CRUD: `python manage.py test tests.profissionais tests.consultas`
- Apenas integração (B2B): `python manage.py test tests.integracao`
- Apenas regressão: `python manage.py test tests.regressao`
- Apenas contrato: `python manage.py test tests.contrato`

## CI/CD
[Resumo do pipeline — SDD-06 — link para o workflow YAML]

## Deploy (staging e produção)
[Resumo da arquitetura EC2 + ECR + Nginx — SDD-07]

## Rollback
[Procedimento real, comando a comando — SDD-07, RN-07]

## Decisões técnicas
[Lista com justificativa — ver tabela abaixo]

## Limitações conhecidas e próximos passos
- CloudWatch não implementado (decisão consciente de escopo/prazo)
- Staging e produção na mesma instância EC2 (ver justificativa no SDD-07)
- Processamento assíncrono de notificação (Celery/Redis) não implementado — candidato natural de evolução
- [Outras limitações reais identificadas durante a implementação]

## Metodologia de desenvolvimento
Este projeto foi desenvolvido usando Spec-Driven Development (SDD),
com apoio do Claude Code no processo de implementação. Todas as
especificações estão documentadas em `docs/specs/`, seguindo o
formato RN (Regra de Negócio) → CA (Critério de Aceite) → Teste,
garantindo rastreabilidade entre requisito e código.

## Estrutura do repositório
[Reaproveitar a árvore da seção 7 do CLAUDE.md]
```

**Tabela de decisões técnicas (RN-02 — a preencher no README real, exemplo do formato esperado):**

| Decisão | Justificativa | SDD |
|---|---|---|
| `on_delete=PROTECT` em Consulta→Profissional | Evita perda silenciosa de histórico de saúde | SDD-02 |
| Autenticação obrigatória também em GET | Dados de profissionais/consultas de saúde não devem ficar públicos, mesmo sendo além do mínimo pedido | SDD-04 |
| Rate limiting com throttle dedicado ao login | Login é alvo natural de força bruta | SDD-04 |
| EC2 única para staging+produção | Prazo do desafio; trade-off documentado, produção real usaria instâncias/RDS separados | SDD-07 |
| Rollback via retag de imagem ECR | Evita rebuild, restaura versão testada anteriormente em minutos | SDD-07 |

**Matriz de rastreabilidade de alto nível (RN-06):**

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

## Checklist de implementação

- [ ] Todo comando do README testado manualmente antes da entrega
- [ ] Seção de decisões técnicas cobre ao menos as 5 decisões da tabela de referência
- [ ] Seção de metodologia SDD/IA presente, sem overclaim nem omissão
- [ ] Seção de limitações conhecidas presente e enquadrada como decisão consciente
- [ ] Rollback documentado é idêntico ao implementado no SDD-07 (não teórico)
- [ ] Matriz de rastreabilidade SDD → critério do desafio presente
- [ ] Link para `/api/docs/` incluído, se o SDD-08 tiver sido implementado
- [ ] Badge de status do GitHub Actions no topo do README (opcional, mas profissionaliza)
