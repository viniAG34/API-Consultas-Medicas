# Convenções de Código — Python/Django/DRF
> ADR de decisões de código para o projeto Lacrei Saúde. Diferente dos SDDs (que definem
> comportamento — RN/CA), este documento define **como o código é escrito** — estrutura,
> estilo de controle de fluxo, tratamento de erro. Aplica-se a toda implementação a partir
> do SDD-03 (o primeiro que contém lógica de aplicação além de model puro).
> Última atualização: 2026-07-10

---

## 1. Estrutura Orientada a Objetos — camadas e responsabilidade única

O projeto usa **Service Layer** como camada intermediária sempre que a lógica ultrapassar
validação simples de campo — já previsto no CLAUDE.md, formalizado aqui com regras concretas.

### 1.1 Quando criar um `services.py`

| Situação | Onde vive |
|---|---|
| Validar formato/obrigatoriedade de 1-2 campos | `serializer.validate_<campo>()` ou `validate()` |
| Regra que cruza múltiplas entidades ou faz mais de uma query | `apps/<app>/services.py` |
| Lógica reaproveitada por mais de uma view/serializer | `apps/<app>/services.py` |
| Cálculo, decisão ou transformação sem I/O | Função pura, mesmo arquivo do serviço, mas separada e testável isoladamente |

**Exemplo concreto — verificação de conflito de horário (hoje dentro do `serializer.validate()`
no SDD-03):** à medida que a regra crescer (ex: considerar duração da consulta, não só o
horário exato), ela migra para `apps/consultas/services.py`:

```python
# apps/consultas/services.py
from apps.consultas.models import Consulta
from apps.core.exceptions import ErroConflitoHorario


class ServicoAgendamento:
    """Orquestra regras de negócio de Consulta que ultrapassam validação de campo único."""

    @staticmethod
    def verificar_conflito_horario(profissional_id: str, data_hora, ignorar_id: str | None = None) -> None:
        conflito = Consulta.objects.filter(profissional_id=profissional_id, data_hora=data_hora)
        if ignorar_id:
            conflito = conflito.exclude(pk=ignorar_id)

        if conflito.exists():
            raise ErroConflitoHorario(profissional_id=profissional_id, data_hora=data_hora)
```

O serializer chama o serviço, não reimplementa a regra:

```python
# apps/consultas/serializers.py
def validate(self, dados):
    profissional = dados.get("profissional", getattr(self.instance, "profissional", None))
    data_hora = dados.get("data_hora", getattr(self.instance, "data_hora", None))

    ServicoAgendamento.verificar_conflito_horario(
        profissional_id=profissional.pk if profissional else None,
        data_hora=data_hora,
        ignorar_id=self.instance.pk if self.instance else None,
    )
    return dados
```

**Por que método estático, não instância com `__init__`:** o serviço não guarda estado entre
chamadas — instanciar `ServicoAgendamento()` sem necessidade seria complexidade sem ganho.
Só vira classe com estado se precisar compor múltiplas operações relacionadas em sequência
(ex: um "orquestrador" de agendamento que abre transação, valida, cria e notifica).

### 1.2 O que NÃO vira classe

Nem toda função precisa de uma classe ao redor. Uma função pura de validação (`validar_uf`,
`normalizar_telefone`) fica solta em `apps/core/utils.py`, sem classe container — criar uma
classe só para agrupar métodos estáticos sem estado é over-engineering.

### 1.3 Camadas e fluxo de dependência (reforça `docs/visao-geral.md`, seção 4)

```
view (HTTP: request/response, status code)
  → serializer (validação de forma + delega regra de negócio)
    → service (regra de negócio que cruza entidades — quando existir)
      → model (Django ORM — única camada que toca o banco)
```

Uma camada só chama a camada imediatamente abaixo. `views.py` nunca importa `models.py`
diretamente para lógica de negócio (pode usar `queryset = Model.objects.all()` para leitura
simples) — regra de escrita/validação sempre passa por serializer → service.

---

## 2. Dependências explícitas, sem container de DI

**Decisão:** o projeto não usa framework de injeção de dependência (`python-dependency-injector`,
`punq`, etc.). Para o tamanho e vida útil deste projeto, isso adicionaria complexidade sem
benefício proporcional. Em vez disso:

- **Dependências passam como parâmetro**, nunca como import escondido dentro do corpo de uma
  função quando evitável:
  ```python
  # Preferir:
  def verificar_conflito_horario(profissional_id, data_hora, queryset=None):
      queryset = queryset if queryset is not None else Consulta.objects.all()
      ...

  # Evitar (acopla a função a uma fonte de dados fixa, dificulta teste):
  def verificar_conflito_horario(profissional_id, data_hora):
      from apps.consultas.models import Consulta  # import escondido no meio da função
      ...
  ```
  Exceção aceitável: imports tardios para **quebrar import circular** entre apps (ex:
  `apps/profissionais` importando algo de `apps/consultas` só dentro de uma função específica)
  — isso é diferente de esconder uma dependência por preguiça de declarar no topo do arquivo.

- **Sem Service Locator:** nenhum registro global tipo `container.resolve(ServicoX)`. Se uma
  view precisa de um serviço, ela importa a classe/função diretamente no topo do arquivo.

- **Sem estado mutável em nível de módulo** fora do necessário (ex: nunca um `_cache = {}`
  global mutável em `services.py` — se precisar de cache, usar o framework de cache do Django
  explicitamente, nunca uma variável solta no módulo).

- **Configuração vem de `settings`/`constantes.py`, nunca hardcoded dentro da lógica** — isso
  já é regra do CLAUDE.md, reforçado aqui como parte do princípio de dependência explícita:
  uma constante importada é uma dependência declarada, um número mágico é uma dependência
  escondida.

---

## 3. Controle de fluxo

### 3.1 Guard clauses (`if not` + `return`/`raise`) em vez de encadeamento de `if`

**Sempre** early return. Nunca aninhar mais de 1 nível de `if` dentro de uma função — se
chegar ao segundo nível, é sinal de extrair uma função ou usar guard clause.

```python
# EVITAR — encadeamento aninhado
def processar(profissional, dados):
    if profissional:
        if profissional.ativo:
            if dados.get("data_hora"):
                # lógica principal, 3 níveis de indentação
                ...
            else:
                raise ValueError("data_hora obrigatória")
        else:
            raise ValueError("profissional inativo")
    else:
        raise ValueError("profissional não encontrado")

# PREFERIR — guard clauses, lógica principal sem indentação extra
def processar(profissional, dados):
    if not profissional:
        raise ErroRecursoNaoEncontrado("profissional")
    if not profissional.ativo:
        raise ErroRegraNegocio("profissional inativo")
    if not dados.get("data_hora"):
        raise ErroValidacao("data_hora obrigatória")

    # lógica principal, sem indentação extra
    ...
```

### 3.2 Ternário — só para atribuição simples de 1 linha, nunca aninhado

```python
# OK — atribuição condicional simples, lê-se em uma linha
identificador_usuario = usuario.username if usuario and usuario.is_authenticated else "anonimo"

# PROIBIDO — ternário aninhado, ilegível
status_cor = "vermelho" if x > 80 else "amarelo" if x > 60 else "verde"  # NÃO FAZER

# PREFERIR match/case ou dict de mapeamento para 3+ ramos (ver 3.3)
```

Regra prática: se o ternário não cabe confortavelmente em uma linha de até ~100 caracteres,
ou se você precisaria de um segundo `if`/`else` dentro dele, não é mais candidato a ternário
— vira `if/elif` explícito ou `match/case`.

### 3.3 `match/case` para despacho por tipo/valor (em vez de `if/elif` longo)

Usado especialmente na composição de exceções (seção 4) e em qualquer decisão com 3+ ramos
mutuamente exclusivos.

```python
# apps/core/exception_handler.py — implementação real, ver SDD-04 para o arquivo completo
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler
from apps.core.exceptions import ErroAplicacao


def tratar_erro_global(exc, context):
    match exc:
        case ErroAplicacao():
            # Uma única cláusula cobre toda a hierarquia — cada subclasse já carrega
            # seu próprio status_http (seção 4), então não há status hardcoded aqui.
            return Response({"detail": exc.mensagem}, status=exc.status_http)
        case _:
            resposta = drf_exception_handler(exc, context)
            if resposta is not None:
                return resposta
            return Response({"detail": "Erro interno do servidor."}, status=500)
```

> **Nota:** o `match/case` aqui casa uma única vez em `ErroAplicacao()` (não em cada
> subclasse individualmente) — o polimorfismo de `status_http` já resolve a diferença entre
> `ErroConflitoHorario` (400), `ErroRecursoProtegido` (400) e `ErroRecursoNaoEncontrado` (404).
> Casar subclasse por subclasse só faria sentido se cada uma precisasse de um formato de
> resposta genuinamente diferente — o que não é o caso aqui. Ver SDD-04, RN-17, para a versão
> completa com logging estruturado.

Isso substitui o que antes era um `try/except ProtectedError` isolado dentro da view (SDD-03)
— agora é um ponto único de despacho, e a view nem precisa saber que `ProtectedError` existe
(ela levanta `ErroRecursoProtegido`, uma exceção do próprio domínio da aplicação).

### 3.4 Zero `except Exception` genérico sem re-raise ou log com contexto

```python
# PROIBIDO — engole a exceção original silenciosamente
try:
    ServicoAgendamento.verificar_conflito_horario(...)
except Exception:
    pass

# OK — captura específica, ou log com contexto antes de propagar/converter
try:
    ServicoAgendamento.verificar_conflito_horario(...)
except ErroConflitoHorario as e:
    logger.warning("Conflito de horário detectado", extra={"profissional_id": ..., "erro": str(e)})
    raise
```

---

## 4. Hierarquia de exceções — classe de erro organizada

**Decisão central:** o projeto define uma hierarquia própria de exceções de domínio em
`apps/core/exceptions.py`, desacoplada das exceções do Django/DRF. Views e serializers
levantam exceções do domínio (`ErroConflitoHorario`, `ErroRecursoProtegido`, etc.) — a
tradução para status HTTP acontece em **um único lugar** (`tratar_erro_global`, via
`match/case`, seção 3.3), nunca espalhada em `try/except` por view.

```python
# apps/core/exceptions.py

class ErroAplicacao(Exception):
    """
    Base de toda exceção de domínio da aplicação. Nunca instanciada diretamente —
    sempre uma subclasse específica. Composição, não herança múltipla: cada subclasse
    carrega os dados relevantes ao próprio erro via __init__, não via atributos soltos
    setados depois.
    """
    status_http: int = 500

    def __init__(self, mensagem: str, **contexto):
        super().__init__(mensagem)
        self.mensagem = mensagem
        self.contexto = contexto  # dict livre — usado no log estruturado (SDD-04)


class ErroValidacao(ErroAplicacao):
    """Entrada inválida que não corresponde a uma regra de negócio específica — 400."""
    status_http = 400


class ErroRegraNegocio(ErroAplicacao):
    """Violação de uma regra de negócio explícita (RN de algum SDD) — 400."""
    status_http = 400


class ErroConflitoHorario(ErroRegraNegocio):
    """Duas consultas no mesmo horário para o mesmo profissional (SDD-03, RN-11) — 400."""

    def __init__(self, profissional_id: str, data_hora):
        super().__init__(
            f"Profissional já possui consulta marcada em {data_hora}.",
            profissional_id=profissional_id,
            data_hora=str(data_hora),
        )


class ErroRecursoProtegido(ErroAplicacao):
    """
    Exclusão bloqueada por integridade referencial (ex: Profissional com Consultas —
    SDD-02, RN-04). Composição: envolve o ProtectedError original do Django como causa,
    em vez de recriar a informação.
    """
    status_http = 400

    def __init__(self, mensagem: str, causa_original: Exception | None = None):
        super().__init__(mensagem)
        self.__cause__ = causa_original


class ErroRecursoNaoEncontrado(ErroAplicacao):
    """Recurso referenciado não existe (ex: profissional_id inválido em uma FK) — 404."""
    status_http = 404
```

### 4.1 Por que "compõe" em vez de herdar de `APIException`/`ValidationError` do DRF

Herdar diretamente de `rest_framework.exceptions.APIException` acopla toda a camada de
domínio (services, serializers) ao DRF — se um dia uma regra de negócio precisar rodar fora
do contexto HTTP (ex: um management command, um script de migração de dados), a exceção de
domínio continua utilizável sem carregar bagagem de "resposta HTTP" junto. A composição
acontece só na borda (`tratar_erro_global`), que traduz `ErroAplicacao.status_http` +
`ErroAplicacao.mensagem` para uma `Response` do DRF. Isso é o princípio de inversão de
dependência (SOLID "D") aplicado a tratamento de erro: o domínio não depende do framework
web, o framework web depende do domínio.

### 4.2 Onde cada camada levanta o quê

| Camada | Pode levantar | Nunca levanta |
|---|---|---|
| `models.py` | Exceções nativas do Django (`ValidationError` de `full_clean()`, se usado) | Exceções de `apps/core/exceptions.py` (model não conhece a camada de aplicação) |
| `services.py` | `ErroRegraNegocio` e subclasses, `ErroRecursoNaoEncontrado` | `ValidationError` do DRF diretamente |
| `serializers.py` | Repassa exceções do service; pode levantar `ErroValidacao` para casos próprios de forma | `HTTPException` genérico |
| `views.py` | Nada — delega tudo para serializer/service; captura `ProtectedError` do Django e converte para `ErroRecursoProtegido` no ponto exato onde o Django a levanta (ORM `.delete()`) | Qualquer lógica de decisão de status HTTP fora do `tratar_erro_global` |
| `apps/core/exception_handler.py` | Traduz `ErroAplicacao` → `Response` via `match/case` | — (é o único lugar que conhece a tradução completa) |

---

## 5. Outras boas práticas aplicadas

- **Type hints em toda função de service/util** (views e serializers seguem convenção padrão
  do DRF, que já é implicitamente tipada pelos schemas) — reforça CLAUDE.md seção 2.
- **Funções pequenas, um verbo, uma responsabilidade** — se o nome da função tem "e"
  (`validar_e_salvar`), é sinal de duas responsabilidades — dividir em duas funções.
- **Dataclasses para agrupar parâmetros relacionados**, em vez de funções com 5+ argumentos
  posicionais soltos:
  ```python
  from dataclasses import dataclass

  @dataclass(frozen=True)
  class FiltroConsultas:
      profissional_id: str | None = None
      data_inicio: str | None = None
      data_fim: str | None = None
  ```
  Usado quando o mesmo agrupamento de parâmetros aparece em mais de um lugar (ex: filtro de
  listagem reaproveitado entre a view e um futuro export/relatório).
- **Nenhuma função de serviço recebe `request` do Django/DRF diretamente** — a view extrai o
  que for necessário (`query_params`, `user`) e passa como argumento simples. Isso mantém o
  service testável sem precisar montar um `HttpRequest` fake em teste unitário.
- **Composição sobre herança** para reaproveitar comportamento entre serializers/views quando
  a herança não representa uma relação "é um" genuína — preferir um serializer/service que
  *usa* outro a criar uma cadeia de herança artificial só para reaproveitar código.

---

## 6. Checklist de revisão de código (por PR/sessão do Claude Code)

- [ ] Nenhuma lógica de negócio em `views.py` além de delegação
- [ ] Nenhum `if` aninhado além de 1 nível — guard clauses aplicadas
- [ ] Nenhum ternário aninhado
- [ ] `match/case` usado onde há 3+ ramos de decisão mutuamente exclusivos
- [ ] Toda exceção de domínio levantada é subclasse de `ErroAplicacao`
- [ ] `tratar_erro_global` é o único lugar que faz `match/case` sobre tipos de exceção
- [ ] Nenhum `except Exception` sem log com contexto ou re-raise
- [ ] Nenhuma dependência escondida em import no meio de função (exceto quebra de import circular, comentada como tal)
- [ ] Nenhum estado mutável em nível de módulo
- [ ] Funções de serviço não recebem `request` — apenas os valores já extraídos dele
