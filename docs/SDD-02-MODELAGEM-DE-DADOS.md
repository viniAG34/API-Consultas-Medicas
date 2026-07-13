# SDD-02 — Modelagem de Dados
> Leia SDD-01 antes de implementar.
> Última atualização: 2026-07-09

---

## Responsabilidade

Definir a estrutura de dados das entidades `Profissional` e `Consulta` — campos, tipos, relacionamentos e constraints — via models do Django, formalizando o contrato de dados que sustenta o CRUD (SDD-03) e todos os módulos seguintes.

**Não faz:** não define endpoints, serializers, regras de autenticação ou validação de entrada via API. Define exclusivamente a estrutura persistida no banco.

---

## Regras de negócio

- RN-01: Toda entidade usa nomenclatura de campos em português, seguindo a convenção do projeto (`nome_social`, `profissao`, `logradouro`, `criado_em`, `atualizado_em`).
- RN-02: `Profissional` é uma entidade independente — pode existir sem nenhuma `Consulta` vinculada.
- RN-03: Toda `Consulta` obrigatoriamente pertence a um `Profissional` — não existe consulta órfã (FK não-nula).
- RN-04: A exclusão de um `Profissional` que possui `Consulta`s vinculadas é uma operação protegida — o sistema não permite exclusão em cascata silenciosa de histórico de consultas (decisão de integridade de dados de saúde, não apenas técnica).
- RN-05: O campo de data da consulta armazena data **e hora** (não apenas data), pois consultas médicas têm horário marcado, essencial para evitar conflito de agenda.
- RN-06: Todo registro de `Profissional` e `Consulta` possui timestamps de criação e atualização (`criado_em`, `atualizado_em`), preenchidos automaticamente — nunca editáveis manualmente via API.
- RN-07: O campo `nome_social` do `Profissional` é obrigatório e não pode ser vazio — é o identificador principal da pessoa profissional no sistema.
- RN-08: `email` e `telefone` são campos de contato separados — ao menos um dos dois é obrigatório, validado a nível de aplicação (detalhado no SDD-03), permitindo cadastro flexível conforme o meio de contato disponível do profissional.
- RN-09: O endereço é modelado em campos estruturados (`logradouro`, `numero`, `bairro`, `cidade`, `estado`, `cep`, `complemento`), não como texto livre único — facilita busca, validação de CEP e futura integração com serviços de geolocalização/entrega.
- RN-10: `numero` e `complemento` são os únicos campos de endereço opcionais (nem todo endereço possui complemento, e alguns logradouros não possuem numeração); os demais campos de endereço são obrigatórios.
- RN-11: `registro_profissional` é obrigatório e identifica o registro de classe da pessoa profissional (ex: CRM, CRP, COREN) — não possui validação de formato específico nesta fase, apenas obrigatoriedade de preenchimento.
- RN-12: O campo `data_hora` de `Consulta` possui índice de banco (`db_index=True`), e a combinação `profissional` + `data_hora` possui `UniqueConstraint`, prevenindo duas consultas no mesmo horário para o mesmo profissional — regra detalhada e justificada no SDD-03 (extensões de refinamento), aplicada aqui na modelagem por ser alteração estrutural do model.

---

## Critérios de aceite

- CA-01: Dado o model `Profissional` criado
         Quando executado `python manage.py makemigrations` e `migrate`
         Então a tabela é criada no PostgreSQL com os campos obrigatórios (nome_social, profissao, registro_profissional, logradouro, bairro, cidade, estado, cep) como `NOT NULL`, e `numero`/`complemento` como opcionais

- CA-02: Dado o model `Consulta` criado
         Quando inspecionado o schema da tabela no PostgreSQL
         Então existe uma foreign key `profissional_id` referenciando `Profissional`, com `on_delete=PROTECT`

- CA-03: Dado um `Profissional` com `Consulta`s vinculadas
         Quando tentada a exclusão desse `Profissional` via ORM (`.delete()`)
         Então a operação levanta `ProtectedError` e nenhum registro é removido

- CA-04: Dado um `Profissional` sem nenhuma `Consulta` vinculada
         Quando tentada a exclusão desse `Profissional`
         Então a operação é concluída com sucesso

- CA-05: Dado um novo registro de `Profissional` ou `Consulta` criado
         Quando o registro é salvo
         Então os campos `criado_em` e `atualizado_em` são preenchidos automaticamente com a data/hora atual

- CA-06: Dado um registro existente de `Profissional` ou `Consulta`
         Quando o registro é atualizado
         Então `atualizado_em` reflete a nova data/hora, e `criado_em` permanece inalterado

- CA-07: Dado o campo `data_hora` de uma `Consulta`
         Quando uma consulta é criada com apenas uma data (sem hora)
         Então o sistema exige o componente de hora, pois o campo é `DateTimeField`, não `DateField`

- CA-08: Dado o model `Profissional`
         Quando uma tentativa de criação é feita sem `nome_social` preenchido
         Então a operação falha a nível de banco (`NOT NULL` constraint), sem depender apenas de validação de aplicação

- CA-09: Dado o model `Profissional`
         Quando uma tentativa de criação é feita sem `numero` e sem `complemento`
         Então a operação é concluída com sucesso, pois ambos são opcionais

- CA-10: Dado o model `Profissional`
         Quando uma tentativa de criação é feita sem `registro_profissional`
         Então a operação falha a nível de banco (`NOT NULL` constraint)

- CA-11: Dado o model `Consulta` com a `UniqueConstraint` de `profissional` + `data_hora` aplicada
         Quando executado `python manage.py makemigrations` e `migrate`
         Então o schema do PostgreSQL reflete a constraint de unicidade combinada e o índice em `data_hora`

---

## Erros e exceções

- Guard A (crítico — propaga): tentativa de excluir `Profissional` com `Consulta`s vinculadas → `ProtectedError` propaga até a camada de API (tratada no SDD-03/04 como erro 400 amigável — `ErroRecursoProtegido`, ver CONVENCOES-CODIGO.md)
- Guard B (fallback): nenhum aplicável nesta camada — modelagem de dados não deve conter lógica de fallback, apenas constraints estruturais
- Guard C (silencioso): nenhum aplicável — qualquer violação de integridade de dados nesta camada deve ser visível (Guard A), nunca silenciosa

---

## Referência de implementação

**`apps/profissionais/models.py`:**
```python
from django.db import models


class Profissional(models.Model):
    nome_social = models.CharField(max_length=255)
    profissao = models.CharField(max_length=100)
    registro_profissional = models.CharField(max_length=50)

    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)

    logradouro = models.CharField(max_length=255)
    numero = models.CharField(max_length=20, blank=True)
    bairro = models.CharField(max_length=100)
    cidade = models.CharField(max_length=100)
    estado = models.CharField(max_length=2)
    cep = models.CharField(max_length=9)
    complemento = models.CharField(max_length=255, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome_social"]

    def __str__(self):
        return self.nome_social
```

**`apps/consultas/models.py`:**
```python
from django.db import models


class Consulta(models.Model):
    profissional = models.ForeignKey(
        "profissionais.Profissional",
        on_delete=models.PROTECT,
        related_name="consultas",
    )
    data_hora = models.DateTimeField(db_index=True)  # índice — ver RN-12

    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-data_hora"]
        constraints = [
            models.UniqueConstraint(
                fields=["profissional", "data_hora"],
                name="uniq_profissional_data_hora",  # RN-12 — detalhado no SDD-03
            )
        ]

    def __str__(self):
        return f"{self.profissional.nome_social} — {self.data_hora}"
```

> **Nota de rastreabilidade:** o índice e a constraint acima foram formalizados como RN-12 deste SDD, mas a motivação de negócio (evitar conflito de agenda) e a validação amigável no serializer estão detalhadas no SDD-03 (seção "Extensões de refinamento"). Se implementado na ordem original dos SDDs, isso exige uma migration aditiva após a migration inicial deste SDD-02 — não é preciso reescrever a migration já aplicada.

**Nota sobre `email`/`telefone`:** ambos modelados como `blank=True` a nível de banco (nenhum dos dois é `NOT NULL` isoladamente), pois a regra "ao menos um dos dois obrigatório" é uma validação combinada de campos — não expressável como constraint simples de coluna. Essa validação será implementada no SDD-03, a nível de serializer (`validate()`), retornando erro 400 se ambos vierem vazios.

**Nota sobre `estado`:** `CharField(max_length=2)` para sigla UF (ex: `RN`, `SP`). Validação de sigla válida (lista fechada de UFs) fica a critério do SDD-03 se sobrar tempo — não é bloqueante para o MVP do desafio.

---

## Checklist de implementação

- [ ] Nomenclatura de campos em português, incluindo timestamps (`criado_em`/`atualizado_em`)
- [ ] `on_delete=PROTECT` na FK de `Consulta` para `Profissional`
- [ ] `criado_em`/`atualizado_em` via `auto_now_add`/`auto_now`, não preenchidos manualmente
- [ ] `data_hora` como `DateTimeField`, não `DateField`
- [ ] `numero` e `complemento` opcionais (`blank=True`); demais campos de endereço obrigatórios
- [ ] `email` e `telefone` como `blank=True` no model — obrigatoriedade combinada validada no SDD-03
- [ ] Migrations geradas e aplicadas sem erro (`makemigrations` + `migrate`)
- [ ] Nenhuma lógica de validação de negócio dentro do model além de constraints estruturais (validação combinada fica no SDD-03/serializers)
- [ ] `db_index=True` em `data_hora` e `UniqueConstraint` (profissional + data_hora) aplicados — ver RN-12 e SDD-03
- [ ] Todos os critérios de aceite cobertos por testes (a implementar formalmente no SDD-05, mas podem ser verificados manualmente nesta fase via Django shell)
