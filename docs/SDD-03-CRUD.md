# SDD-03 — CRUD de Profissionais e Consultas
> Leia SDD-01 e SDD-02 antes de implementar.
> Última atualização: 2026-07-09

---

## Responsabilidade

Expor via API RESTful o CRUD completo de `Profissional` e `Consulta`, incluindo o endpoint de busca de consultas por ID do profissional, com validação de entrada via serializers e respostas de erro consistentes.

**Não faz:** não define autenticação/autorização (SDD-04), não define testes formais (SDD-05), não define documentação Swagger (SDD-08). Define exclusivamente os endpoints, serializers e comportamento de validação/erro da API.

---

## Regras de negócio

- RN-01: Todos os endpoints retornam JSON, incluindo respostas de erro.
- RN-02: A criação e atualização de `Profissional` exige `nome_social`, `profissao`, `registro_profissional`, `logradouro`, `bairro`, `cidade`, `estado`, `cep` — conforme obrigatoriedade definida no SDD-02.
- RN-03: A criação e atualização de `Profissional` exige que ao menos um entre `email` e `telefone` esteja preenchido (RN-08 do SDD-02) — validado no serializer via `validate()`.
- RN-04: A criação e atualização de `Consulta` exige `data_hora` e `profissional` (ID de um profissional existente).
- RN-05: Tentativa de criar `Consulta` referenciando `profissional` inexistente retorna erro 400 com mensagem clara, nunca 500.
- RN-06: Tentativa de excluir `Profissional` com `Consulta`s vinculadas retorna erro 400 com mensagem explicando a causa (nunca deixa o `ProtectedError` do Django vazar como 500).
- RN-07: A listagem de `Profissional` e `Consulta` é paginada — nunca retorna todos os registros sem limite, mesmo que a base cresça.
- RN-08: A busca de consultas por profissional é feita via query param (`?profissional=<id>`) no endpoint de listagem de consultas, reaproveitando o mesmo endpoint de listagem — não é uma rota separada.
- RN-09: Campos `criado_em` e `atualizado_em` nunca são aceitos como entrada da API — são somente leitura (`read_only`) em todos os serializers.
- RN-10: Erros de validação retornam 400 com o formato padrão do DRF (dicionário campo → lista de mensagens), nunca uma string genérica de erro.

### Extensões de refinamento (bônus de domínio e performance)

- RN-11: Duas `Consulta`s não podem existir para o mesmo `profissional` no mesmo `data_hora` — constraint de unicidade combinada, prevenindo duplicidade acidental de horário.
- RN-12: A listagem de `Consulta` sempre usa `select_related("profissional")` no queryset, evitando N+1 queries ao serializar o profissional vinculado.
- RN-13: A listagem de `Consulta` aceita filtro opcional por intervalo de data (`?data_inicio=&data_fim=`), combinável com o filtro por `?profissional=` já existente (RN-08).
- RN-14: O campo `data_hora` de `Consulta` possui índice de banco, dado que é o campo mais provável de ser usado em filtros de intervalo/ordenação em uso real.

### Composição de exceções (ver CONVENCOES-CODIGO.md)

- RN-15: Erros de regra de negócio (conflito de horário, exclusão protegida) são levantados como **exceções de domínio** (`apps/core/exceptions.py` — `ErroConflitoHorario`, `ErroRecursoProtegido`), nunca como `rest_framework.exceptions.ValidationError` diretamente em serializer/view. A tradução para status HTTP acontece de forma centralizada no `tratar_erro_global` (SDD-04), via `match/case` — nenhuma view faz esse mapeamento por conta própria.

---

## Critérios de aceite

- CA-01: Dado um payload válido de `Profissional`
         Quando enviado `POST /api/profissionais/`
         Então retorna `201` com o objeto criado, incluindo `id`, `criado_em` e `atualizado_em`

- CA-02: Dado um payload de `Profissional` sem `email` nem `telefone`
         Quando enviado `POST /api/profissionais/`
         Então retorna `400` com mensagem indicando que ao menos um dos dois é obrigatório

- CA-03: Dado um payload de `Profissional` sem `nome_social`
         Quando enviado `POST /api/profissionais/`
         Então retorna `400` com o campo `nome_social` apontado no erro

- CA-04: Dado um `Profissional` existente
         Quando enviado `GET /api/profissionais/{id}/`
         Então retorna `200` com os dados completos do profissional

- CA-05: Dado um ID de profissional inexistente
         Quando enviado `GET /api/profissionais/{id}/`
         Então retorna `404`

- CA-06: Dado um `Profissional` existente
         Quando enviado `PUT /api/profissionais/{id}/` com payload válido
         Então retorna `200` com os dados atualizados e `atualizado_em` alterado

- CA-07: Dado um `Profissional` existente sem consultas vinculadas
         Quando enviado `DELETE /api/profissionais/{id}/`
         Então retorna `204` e o registro deixa de existir

- CA-08: Dado um `Profissional` existente com ao menos uma `Consulta` vinculada
         Quando enviado `DELETE /api/profissionais/{id}/`
         Então retorna `400` com mensagem informando que o profissional possui consultas vinculadas e não pode ser removido

- CA-09: Dado dois ou mais `Profissional` cadastrados
         Quando enviado `GET /api/profissionais/`
         Então retorna `200` com lista paginada, incluindo campos de paginação (`count`, `next`, `previous`, `results`)

- CA-10: Dado um payload válido de `Consulta` referenciando um `profissional` existente
         Quando enviado `POST /api/consultas/`
         Então retorna `201` com o objeto criado, incluindo `id` e o `profissional` vinculado

- CA-11: Dado um payload de `Consulta` referenciando `profissional` inexistente
         Quando enviado `POST /api/consultas/`
         Então retorna `400` com mensagem indicando que o profissional informado não existe

- CA-12: Dado um payload de `Consulta` sem `data_hora`
         Quando enviado `POST /api/consultas/`
         Então retorna `400` com o campo `data_hora` apontado no erro

- CA-13: Dado um profissional com múltiplas consultas cadastradas, e outros profissionais com suas próprias consultas
         Quando enviado `GET /api/consultas/?profissional={id}`
         Então retorna `200` apenas com as consultas daquele profissional específico

- CA-14: Dado um `profissional` sem nenhuma consulta cadastrada
         Quando enviado `GET /api/consultas/?profissional={id}`
         Então retorna `200` com lista vazia (`results: []`), nunca erro

- CA-15: Dado um `id` de consulta existente
         Quando enviado `DELETE /api/consultas/{id}/`
         Então retorna `204` e o registro deixa de existir (exclusão de consulta não é protegida — diferente de profissional)

- CA-16: Dado qualquer payload de criação/atualização tentando enviar `criado_em` ou `atualizado_em`
         Quando a requisição é processada
         Então esses campos são ignorados silenciosamente (read-only), e os valores reais permanecem controlados pelo model

### Extensões de refinamento

- CA-17: Dado um `profissional` com uma `Consulta` já cadastrada em determinado `data_hora`
         Quando enviado `POST /api/consultas/` com o mesmo `profissional` e o mesmo `data_hora`
         Então retorna `400` com mensagem indicando conflito de horário para aquele profissional

- CA-18: Dado o mesmo `data_hora`, mas para um `profissional` diferente
         Quando enviado `POST /api/consultas/`
         Então a criação é permitida normalmente (constraint é por par profissional+horário, não por horário isolado)

- CA-19: Dado `GET /api/consultas/` com múltiplos profissionais cadastrados
         Quando a query é inspecionada (ex: via `django.db.connection.queries` em teste)
         Então o número de queries não cresce proporcionalmente ao número de consultas retornadas (confirma `select_related` aplicado)

- CA-20: Dado consultas cadastradas em datas variadas
         Quando enviado `GET /api/consultas/?data_inicio=2026-08-01&data_fim=2026-08-15`
         Então retorna apenas as consultas com `data_hora` dentro do intervalo (inclusive), combinável com `?profissional=`

---

## Erros e exceções

- Guard A (crítico — propaga): erro inesperado não tratado (ex: falha de conexão com banco durante a requisição) → propaga para o exception handler padrão do DRF, retornando 500 genérico sem vazar stack trace ao cliente
- Guard B.1 (fallback): `ProtectedError` (exceção nativa do Django) ao tentar excluir `Profissional` com consultas vinculadas → capturada na view no ponto exato onde o Django a levanta (`.delete()`), e **convertida em `ErroRecursoProtegido`** (exceção de domínio, `apps/core/exceptions.py`) — a tradução para 400 amigável acontece depois, de forma centralizada, no `tratar_erro_global` (SDD-04, RN-15)
- Guard B.2 (fallback): violação de `UniqueConstraint` (profissional + data_hora) ao criar/atualizar `Consulta` → detectada no serializer via `validate()`, que levanta **`ErroConflitoHorario`** (exceção de domínio) em vez de consultar o banco e deixar o `IntegrityError` vazar — a constraint de banco continua como segunda barreira, redundante mas intencional
- Guard C (silencioso): tentativa de enviar `criado_em`/`atualizado_em` no payload → campo ignorado por ser `read_only`, sem erro e sem log (comportamento padrão esperado do DRF, não uma falha)

---

## Referência de implementação

**`apps/profissionais/serializers.py`:**
```python
from rest_framework import serializers
from .models import Profissional


class ProfissionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profissional
        fields = [
            "id", "nome_social", "profissao", "registro_profissional",
            "email", "telefone",
            "logradouro", "numero", "bairro", "cidade", "estado", "cep", "complemento",
            "criado_em", "atualizado_em",
        ]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate(self, dados):
        if not dados.get("email") and not dados.get("telefone"):
            raise serializers.ValidationError(
                {"contato": "Informe ao menos um meio de contato: email ou telefone."}
            )
        return dados
```

**`apps/profissionais/views.py`:**
```python
from rest_framework import viewsets
from django.db.models import ProtectedError
from apps.core.exceptions import ErroRecursoProtegido
from .models import Profissional
from .serializers import ProfissionalSerializer


class ProfissionalViewSet(viewsets.ModelViewSet):
    queryset = Profissional.objects.all()
    serializer_class = ProfissionalSerializer

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except ProtectedError as e:
            # Ponto exato onde o Django levanta a exceção nativa — convertida aqui
            # para a exceção de domínio (ver CONVENCOES-CODIGO.md, seção 4.2).
            # A tradução para 400 acontece centralizada no tratar_erro_global (SDD-04).
            raise ErroRecursoProtegido(
                "Este profissional possui consultas vinculadas e não pode ser removido.",
                causa_original=e,
            )
```

**`apps/consultas/serializers.py`:**
```python
from rest_framework import serializers
from .models import Consulta


class ConsultaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consulta
        fields = ["id", "data_hora", "profissional", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]
```

**`apps/consultas/views.py`:**
```python
from rest_framework import viewsets
from .models import Consulta
from .serializers import ConsultaSerializer


class ConsultaViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultaSerializer

    def get_queryset(self):
        queryset = Consulta.objects.all()
        id_profissional = self.request.query_params.get("profissional")
        if id_profissional:
            queryset = queryset.filter(profissional_id=id_profissional)
        return queryset
```

**`config/urls.py` (routers):**
```python
from rest_framework.routers import DefaultRouter
from apps.profissionais.views import ProfissionalViewSet
from apps.consultas.views import ConsultaViewSet

router = DefaultRouter()
router.register(r"profissionais", ProfissionalViewSet, basename="profissional")
router.register(r"consultas", ConsultaViewSet, basename="consulta")

urlpatterns = [
    # ...
    *router.urls,
]
```

**Paginação (RN-07) — em `apps/core/constantes.py` e `settings/base.py`:**
```python
# apps/core/constantes.py
LIMITE_PAGINACAO_PADRAO = 20  # SDD-03, RN-07

# settings/base.py
from apps.core.constantes import LIMITE_PAGINACAO_PADRAO

REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": LIMITE_PAGINACAO_PADRAO,
}
```

**Nota sobre validação de `profissional` inexistente em `Consulta` (RN-05):** o `PrimaryKeyRelatedField` padrão do DRF já retorna 400 automaticamente quando o ID referenciado não existe — nenhuma validação manual adicional é necessária além do serializer padrão, desde que o `queryset` do campo `profissional` esteja corretamente vinculado ao `ModelSerializer`.

> **Atenção:** as versões de `ConsultaSerializer` e `ConsultaViewSet` acima são a base do CRUD.
> A seção "Extensões de refinamento" logo abaixo **substitui** essas duas classes pela versão
> final (com validação de conflito de horário e `select_related`) — implemente diretamente a
> versão final, a base acima serve só para entender a evolução incremental.

---

### Extensões de refinamento — referência de implementação

> O model de `Consulta` com `db_index` e `UniqueConstraint` já está definido por extenso no
> **SDD-02** (referência de implementação, RN-12) — não repetido aqui para evitar duas fontes
> de verdade divergentes. O que pertence a este SDD-03 é a validação amigável no serializer
> e o ajuste na view, abaixo.

**`apps/consultas/serializers.py` — validação de conflito amigável (Guard B.2):**
```python
from rest_framework import serializers
from apps.core.exceptions import ErroConflitoHorario
from .models import Consulta


class ConsultaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Consulta
        fields = ["id", "data_hora", "profissional", "criado_em", "atualizado_em"]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    def validate(self, dados):
        profissional = dados.get("profissional", getattr(self.instance, "profissional", None))
        data_hora = dados.get("data_hora", getattr(self.instance, "data_hora", None))

        conflito = Consulta.objects.filter(profissional=profissional, data_hora=data_hora)
        if self.instance:
            conflito = conflito.exclude(pk=self.instance.pk)

        if conflito.exists():
            # Exceção de domínio, não rest_framework.exceptions.ValidationError diretamente
            # (ver CONVENCOES-CODIGO.md, seção 4) — tratar_erro_global (SDD-04) traduz para 400.
            raise ErroConflitoHorario(
                profissional_id=str(profissional.pk) if profissional else None,
                data_hora=data_hora,
            )
        return dados
```

**`apps/consultas/views.py` — `select_related` e filtro de intervalo de data:**
```python
from rest_framework import viewsets
from .models import Consulta
from .serializers import ConsultaSerializer


class ConsultaViewSet(viewsets.ModelViewSet):
    serializer_class = ConsultaSerializer

    def get_queryset(self):
        queryset = Consulta.objects.select_related("profissional").all()  # RN-12

        id_profissional = self.request.query_params.get("profissional")
        if id_profissional:
            queryset = queryset.filter(profissional_id=id_profissional)

        data_inicio = self.request.query_params.get("data_inicio")
        data_fim = self.request.query_params.get("data_fim")
        if data_inicio:
            queryset = queryset.filter(data_hora__date__gte=data_inicio)
        if data_fim:
            queryset = queryset.filter(data_hora__date__lte=data_fim)

        return queryset
```

**Nota sobre a migration retroativa:** como esse refinamento altera o model já definido no SDD-02, é necessário rodar `makemigrations` novamente após esse ajuste — a nova migration é aditiva (índice + constraint), não substitui a migration original do SDD-02.

**Armadilha conhecida do DRF — `UniqueTogetherValidator` automático:** o `ModelSerializer` do DRF
inspeciona a `UniqueConstraint` do model (`profissional` + `data_hora`) e gera automaticamente
um `UniqueTogetherValidator`. Esse validador roda **antes** do `validate()` customizado acima —
ou seja, ele detecta o conflito de horário primeiro e levanta `rest_framework.exceptions.ValidationError`
diretamente, com uma mensagem genérica do DRF, nunca chegando a instanciar `ErroConflitoHorario`.
Isso viola RN-15 (erro de conflito de horário deve ser uma exceção de domínio, traduzida
centralmente pelo `tratar_erro_global`). A correção é `validators = []` no `Meta` do
`ConsultaSerializer` (já implementado em `apps/consultas/serializers.py`), desativando
explicitamente esse validador automático — a constraint de banco continua como segunda
barreira (Guard B.2), redundante mas intencional. Registrado aqui para quem reler este SDD no
futuro e se perguntar por que `validators = []` aparece no serializer sem uma explicação óbvia
à primeira vista.

---

## Checklist de implementação

- [ ] Nomenclatura em português nos serializers, views e mensagens de erro
- [ ] `criado_em`/`atualizado_em` como `read_only_fields` em ambos os serializers
- [ ] Validação de `email`/`telefone` combinada implementada em `ProfissionalSerializer.validate()`
- [ ] `ProtectedError` capturado e convertido em 400 amigável no `ProfissionalViewSet`
- [ ] Filtro por `?profissional=<id>` implementado em `ConsultaViewSet.get_queryset()`
- [ ] Paginação configurada globalmente via `LIMITE_PAGINACAO_PADRAO` em `constantes.py` (zero número mágico solto no settings)
- [ ] Todos os critérios de aceite cobertos por testes (formalizado no SDD-05)
- [ ] Nenhuma lógica de autenticação/permissão neste SDD (fica isolada no SDD-04)
- [ ] `UniqueConstraint` (profissional + data_hora) adicionada ao model e nova migration gerada
- [ ] Conflito de horário validado no serializer, nunca deixando `IntegrityError` vazar como 500
- [ ] Exceções de domínio (`ErroRecursoProtegido`, `ErroConflitoHorario`) importadas de `apps/core/exceptions.py` — nunca `rest_framework.exceptions.ValidationError` levantada diretamente para esses casos
- [ ] `select_related("profissional")` aplicado no queryset de `Consulta`
- [ ] Filtros `?data_inicio=` e `?data_fim=` funcionando de forma combinável com `?profissional=`
- [ ] `db_index=True` aplicado ao campo `data_hora`
