# SDD-05 — Testes Automatizados
> Leia SDD-01, SDD-02, SDD-03 e SDD-04 antes de implementar.
> Última atualização: 2026-07-09

---

## Responsabilidade

Cobrir com `APITestCase` todos os critérios de aceite definidos nos SDDs-02, 03 e 04, organizados por tipo de teste em pastas próprias: **unitários/CRUD**, **erros**, **regressão**, **integração entre módulos** e **contrato de API**.

**Não faz:** não define nenhuma regra de negócio nova — cada teste aqui referencia um CA já existente em outro SDD. Se um teste exigir uma regra não documentada, a regra deve ser adicionada ao SDD correspondente antes do teste ser escrito.

---

## Regras de negócio

- RN-01: Todo teste referencia explicitamente, em docstring ou comentário, o CA e o SDD de origem (rastreabilidade RN→CA→teste do método formalizado).
- RN-02: Nomes de teste são derivados do critério de aceite (`test_<contexto>_<resultado_esperado>`), nunca nomeados arbitrariamente.
- RN-03: Nenhum teste depende de estado deixado por outro teste — cada `APITestCase` usa `setUp()` próprio, sem fixtures globais mutáveis compartilhadas entre classes.
- RN-04: Testes de **CRUD e erro** vivem na pasta do módulo correspondente (`tests/profissionais/`, `tests/consultas/`); testes de **integração**, **regressão** e **contrato** vivem em pastas próprias na raiz de `tests/`, por não pertencerem a um único módulo.
- RN-05: **Testes de regressão** existem para proteger bugs específicos já identificados e corrigidos durante o desenvolvimento — cada teste de regressão referencia a causa raiz do bug que ele impede de voltar.
- RN-06: **Testes de integração (B2B — fluxo completo)** cobrem cenários de ponta a ponta que atravessam mais de um módulo (ex: criar profissional → criar consulta vinculada → excluir profissional deve falhar → excluir consulta → excluir profissional deve funcionar).
- RN-07: **Testes de contrato** verificam que o formato de resposta da API (campos presentes, tipos, estrutura de paginação e erro) permanece estável — protegem contra mudanças acidentais no shape do JSON que quebrariam um consumidor externo da API.
- RN-08: A cobertura mínima exigida cobre: CRUD completo de profissionais e consultas, casos de erro (dados ausentes/inválidos), e os fluxos de autenticação/segurança do SDD-04.
- RN-09: Nenhum teste depende de serviço externo real (ex: banco de produção) — todos rodam contra o banco de teste isolado que o Django cria automaticamente.
- RN-10: Testes de regressão e integração são executados no mesmo pipeline dos testes unitários (SDD-06) — não são uma suíte opcional separada.
- RN-11: Toda classe de teste que exercita endpoint protegido herda de `APITestCaseAutenticado` (base própria com usuário e token já configurados em `setUp()`), nunca `APITestCase` puro — pois o `IsAuthenticated` global (SDD-04, RN-02) rejeitaria a requisição com 401 antes mesmo de chegar à lógica testada. Exceção: `tests/seguranca/test_autenticacao.py`, que testa deliberadamente o comportamento sem autenticação, e `tests/seguranca/test_health_check.py`, que testa o acesso público ao `/health/` (SDD-04, RN-15).

---

## Critérios de aceite

- CA-01: Dado o comando `python manage.py test`
         Quando executado na raiz do projeto
         Então todos os testes de `tests/profissionais/`, `tests/consultas/`, `tests/integracao/`, `tests/regressao/` e `tests/contrato/` rodam e passam

- CA-02: Dado um teste de CRUD de `Profissional`
         Quando executado isoladamente (`python manage.py test tests.profissionais.test_crud`)
         Então passa sem depender de nenhum outro teste ter rodado antes

- CA-03: Dado o critério CA-08 do SDD-03 (exclusão de profissional com consulta vinculada)
         Quando testado em `tests/profissionais/test_erros.py`
         Então o teste verifica especificamente o status `400` e a mensagem de erro, não apenas "não é 200"

- CA-04: Dado o fluxo completo profissional → consulta → tentativa de exclusão → exclusão da consulta → exclusão do profissional
         Quando executado em `tests/integracao/test_fluxo_profissional_consulta.py`
         Então cada etapa do fluxo passa na ordem correta, validando o estado do banco entre os passos

- CA-05: Dado um bug já corrigido (ex: um CASE registrado durante o desenvolvimento)
         Quando o teste de regressão correspondente roda
         Então ele falha se o bug for reintroduzido, e passa no comportamento correto atual

- CA-06: Dado o endpoint `GET /api/profissionais/`
         Quando testado em `tests/contrato/test_contrato_profissionais.py`
         Então a resposta contém exatamente os campos esperados (`count`, `next`, `previous`, `results`) e cada item de `results` contém todos os campos do serializer, nem mais nem menos

- CA-07: Dado o endpoint de erro de validação (ex: `POST /api/profissionais/` sem `nome_social`)
         Quando testado em `tests/contrato/test_contrato_erros.py`
         Então a resposta segue o formato padrão do DRF (`{"campo": ["mensagem"]}`), garantindo que um consumidor externo sempre saiba onde procurar o erro

- CA-08: Dado o `pytest`/`manage.py test` rodando com `--verbosity=2`
         Quando a suíte completa é executada
         Então nenhum teste é marcado como `skipped` sem justificativa explícita em comentário

- CA-09: Dado qualquer teste de endpoint protegido escrito herdando de `APITestCaseAutenticado`
         Quando executado
         Então a requisição já chega autenticada (sem retornar 401 por falta de token), permitindo testar a lógica de negócio real do endpoint

---

## Erros e exceções

- Guard A (crítico — propaga): falha de setup do banco de teste (ex: migrations quebradas) → suíte inteira falha imediatamente, impedindo runs parciais enganosos
- Guard B (fallback): nenhum aplicável — testes não devem ter fallback silencioso; um teste que "quase passa" deve falhar, não ser tolerado
- Guard C (silencioso): nenhum aplicável nesta camada — testes silenciosos que escondem falha são o oposto do objetivo deste SDD

---

## Referência de implementação

**`tests/base.py` — base autenticada obrigatória (RN-11), evita que todo teste repita o boilerplate de login:**
```python
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class APITestCaseAutenticado(APITestCase):
    """
    Base para qualquer teste que exercite endpoint protegido pelo
    IsAuthenticated global (SDD-04, RN-02). Cria um usuário e autentica
    o client automaticamente em setUp() via force_authenticate — evita
    testar o fluxo de token em todo teste de CRUD (isso já é coberto
    isoladamente em tests/seguranca/test_autenticacao.py).
    """

    def setUp(self):
        super().setUp()
        Usuario = get_user_model()
        self.usuario_teste = Usuario.objects.create_user(
            username="usuario_teste", password="senha-teste-nao-usar-em-producao",
        )
        self.client.force_authenticate(user=self.usuario_teste)
```

**Estrutura de pastas de teste:**
```
tests/
├── __init__.py
├── profissionais/
│   ├── __init__.py
│   ├── test_crud.py        ← CA-01 a CA-09 do SDD-03 (parte de Profissional)
│   └── test_erros.py       ← casos de erro específicos de Profissional (CA-02, CA-03, CA-08 do SDD-03)
├── consultas/
│   ├── __init__.py
│   ├── test_crud.py        ← CA-10, CA-13 a CA-15 do SDD-03
│   ├── test_erros.py       ← CA-11, CA-12 do SDD-03
│   └── test_refinamentos.py ← CA-17 a CA-20 do SDD-03 (extensões: conflito de horário, filtro de data)
├── seguranca/
│   ├── __init__.py
│   ├── test_autenticacao.py   ← CA-01 a CA-05 do SDD-04
│   ├── test_rate_limiting.py  ← CA-11 a CA-13 do SDD-04
│   └── test_health_check.py   ← CA-14, CA-15 do SDD-04 (endpoints públicos, sem herdar de APITestCaseAutenticado)
├── integracao/
│   ├── __init__.py
│   └── test_fluxo_profissional_consulta.py   ← RN-06, CA-04 deste SDD
├── regressao/
│   ├── __init__.py
│   └── test_regressao.py                      ← RN-05, CA-05 deste SDD
└── contrato/
    ├── __init__.py
    ├── test_contrato_profissionais.py          ← CA-06 deste SDD
    └── test_contrato_erros.py                  ← CA-07 deste SDD
```

**`tests/profissionais/test_crud.py` — exemplo de nomeação derivada do CA:**
```python
from rest_framework import status
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado


class ProfissionalCRUDTestCase(APITestCaseAutenticado):
    """Cobre SDD-03, CA-01, CA-04, CA-06, CA-07, CA-09."""

    def setUp(self):
        super().setUp()
        self.payload_valido = {
            "nome_social": "Ana Souza",
            "profissao": "Psicóloga",
            "registro_profissional": "CRP-12345",
            "email": "ana@example.com",
            "logradouro": "Rua das Flores",
            "bairro": "Centro",
            "cidade": "Mossoró",
            "estado": "RN",
            "cep": "59600-000",
        }

    def test_criar_profissional_com_payload_valido_retorna_201(self):
        """SDD-03, CA-01."""
        resposta = self.client.post("/api/profissionais/", self.payload_valido)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        self.assertIn("criado_em", resposta.data)
        self.assertIn("atualizado_em", resposta.data)

    def test_excluir_profissional_sem_consultas_retorna_204(self):
        """SDD-03, CA-07."""
        profissional = Profissional.objects.create(**self.payload_valido)
        resposta = self.client.delete(f"/api/profissionais/{profissional.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)
```

**`tests/profissionais/test_erros.py` — exemplo de verificação além de "não é 200" (RN mais rigorosa que o padrão):**
```python
from rest_framework import status
from apps.profissionais.models import Profissional
from apps.consultas.models import Consulta
from tests.base import APITestCaseAutenticado


class ProfissionalErrosTestCase(APITestCaseAutenticado):
    """Cobre SDD-03, CA-02, CA-03, CA-08."""

    def test_criar_profissional_sem_contato_retorna_400_com_mensagem_especifica(self):
        """SDD-03, CA-02."""
        payload = {
            "nome_social": "Ana Souza", "profissao": "Psicóloga",
            "registro_profissional": "CRP-12345",
            "logradouro": "Rua das Flores", "bairro": "Centro",
            "cidade": "Mossoró", "estado": "RN", "cep": "59600-000",
        }
        resposta = self.client.post("/api/profissionais/", payload)
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("contato", resposta.data)

    def test_excluir_profissional_com_consulta_vinculada_retorna_400(self):
        """SDD-03, CA-08 — verifica status E mensagem, não apenas 'não é 200'."""
        profissional = Profissional.objects.create(
            nome_social="Ana Souza", profissao="Psicóloga",
            registro_profissional="CRP-12345", email="ana@example.com",
            logradouro="Rua das Flores", bairro="Centro",
            cidade="Mossoró", estado="RN", cep="59600-000",
        )
        Consulta.objects.create(profissional=profissional, data_hora="2026-08-01T10:00:00Z")

        resposta = self.client.delete(f"/api/profissionais/{profissional.id}/")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("vinculadas", str(resposta.data).lower())
```

**`tests/integracao/test_fluxo_profissional_consulta.py` — testes B2B (fluxo completo ponta a ponta):**
```python
from rest_framework import status
from tests.base import APITestCaseAutenticado


class FluxoProfissionalConsultaTestCase(APITestCaseAutenticado):
    """
    Testes de integração/B2B (RN-06 do SDD-05).
    Cobre o ciclo de vida completo atravessando os módulos
    Profissional e Consulta, incluindo a regra de exclusão protegida
    definida no SDD-02 (RN-04) e SDD-03 (CA-08).
    """

    def test_fluxo_completo_criar_consulta_bloquear_exclusao_liberar_exclusao(self):
        # 1. Cria profissional
        payload_profissional = {
            "nome_social": "Carla Lima", "profissao": "Médica",
            "registro_profissional": "CRM-9876", "telefone": "84999999999",
            "logradouro": "Av. Central", "bairro": "Centro",
            "cidade": "Mossoró", "estado": "RN", "cep": "59600-000",
        }
        resposta = self.client.post("/api/profissionais/", payload_profissional)
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        id_profissional = resposta.data["id"]

        # 2. Cria consulta vinculada
        resposta = self.client.post("/api/consultas/", {
            "profissional": id_profissional, "data_hora": "2026-08-10T14:00:00Z",
        })
        self.assertEqual(resposta.status_code, status.HTTP_201_CREATED)
        id_consulta = resposta.data["id"]

        # 3. Tenta excluir profissional — deve ser bloqueado (integração models + serializers + view)
        resposta = self.client.delete(f"/api/profissionais/{id_profissional}/")
        self.assertEqual(resposta.status_code, status.HTTP_400_BAD_REQUEST)

        # 4. Exclui a consulta
        resposta = self.client.delete(f"/api/consultas/{id_consulta}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

        # 5. Agora a exclusão do profissional deve funcionar
        resposta = self.client.delete(f"/api/profissionais/{id_profissional}/")
        self.assertEqual(resposta.status_code, status.HTTP_204_NO_CONTENT)

    def test_busca_consultas_por_profissional_retorna_apenas_do_profissional_correto(self):
        """Integração entre filtro de Consulta e cadastro de múltiplos Profissionais (SDD-03, CA-13)."""
        resposta_a = self.client.post("/api/profissionais/", {
            "nome_social": "Profissional A", "profissao": "Médica",
            "registro_profissional": "CRM-0001", "email": "a@example.com",
            "logradouro": "Rua A", "bairro": "Centro", "cidade": "Mossoró",
            "estado": "RN", "cep": "59600-000",
        })
        resposta_b = self.client.post("/api/profissionais/", {
            "nome_social": "Profissional B", "profissao": "Médica",
            "registro_profissional": "CRM-0002", "email": "b@example.com",
            "logradouro": "Rua B", "bairro": "Centro", "cidade": "Mossoró",
            "estado": "RN", "cep": "59600-000",
        })
        id_a, id_b = resposta_a.data["id"], resposta_b.data["id"]

        self.client.post("/api/consultas/", {"profissional": id_a, "data_hora": "2026-08-01T10:00:00Z"})
        self.client.post("/api/consultas/", {"profissional": id_b, "data_hora": "2026-08-02T10:00:00Z"})

        resposta = self.client.get(f"/api/consultas/?profissional={id_a}")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(len(resposta.data["results"]), 1)
        self.assertEqual(resposta.data["results"][0]["profissional"], id_a)
```

**`tests/regressao/test_regressao.py` — exemplo de estrutura (a preencher conforme bugs reais forem encontrados durante o desenvolvimento):**
```python
from rest_framework import status
from tests.base import APITestCaseAutenticado


class RegressaoTestCase(APITestCaseAutenticado):
    """
    Testes de regressão (RN-05 do SDD-05).
    Cada teste aqui documenta um bug real encontrado e corrigido,
    para impedir que ele volte em uma futura alteração.

    Formato esperado por teste:
    - Causa raiz do bug
    - Comportamento incorreto observado
    - Comportamento correto esperado (o que este teste garante)
    """

    def test_criado_em_nao_e_sobrescrito_ao_enviar_no_payload_de_atualizacao(self):
        """
        Causa raiz (exemplo hipotético a substituir pelo bug real, se ocorrer):
        um serializer mal configurado poderia aceitar `criado_em` vindo do
        payload de PUT/PATCH, permitindo forjar a data de criação de um registro.
        Este teste garante que o campo permanece read-only mesmo se enviado.
        """
        payload = {
            "nome_social": "Teste Regressão", "profissao": "Médica",
            "registro_profissional": "CRM-0000", "email": "teste@example.com",
            "logradouro": "Rua X", "bairro": "Centro", "cidade": "Mossoró",
            "estado": "RN", "cep": "59600-000",
        }
        resposta = self.client.post("/api/profissionais/", payload)
        id_profissional = resposta.data["id"]
        data_criacao_original = resposta.data["criado_em"]

        resposta_update = self.client.patch(
            f"/api/profissionais/{id_profissional}/",
            {"criado_em": "2000-01-01T00:00:00Z"},
        )
        self.assertEqual(resposta_update.status_code, status.HTTP_200_OK)
        self.assertEqual(resposta_update.data["criado_em"], data_criacao_original)
```

**`tests/contrato/test_contrato_profissionais.py` — exemplo de teste de contrato:**
```python
from rest_framework import status
from apps.profissionais.models import Profissional
from tests.base import APITestCaseAutenticado


class ContratoProfissionaisTestCase(APITestCaseAutenticado):
    """
    Testes de contrato (RN-07 do SDD-05).
    Protegem o formato do JSON retornado — um consumidor externo da API
    depende dessa estrutura permanecer estável.
    """

    CAMPOS_ESPERADOS_PROFISSIONAL = {
        "id", "nome_social", "profissao", "registro_profissional",
        "email", "telefone", "logradouro", "numero", "bairro",
        "cidade", "estado", "cep", "complemento", "criado_em", "atualizado_em",
    }

    def test_listagem_profissionais_segue_contrato_de_paginacao_padrao(self):
        """SDD-05, CA-06."""
        resposta = self.client.get("/api/profissionais/")
        self.assertEqual(resposta.status_code, status.HTTP_200_OK)
        self.assertEqual(set(resposta.data.keys()), {"count", "next", "previous", "results"})

    def test_item_de_profissional_contem_exatamente_os_campos_do_contrato(self):
        """SDD-05, CA-06 — nem mais, nem menos campos que o serializer define."""
        Profissional.objects.create(
            nome_social="Teste", profissao="Médica", registro_profissional="CRM-1",
            email="t@example.com", logradouro="Rua X", bairro="Centro",
            cidade="Mossoró", estado="RN", cep="59600-000",
        )
        resposta = self.client.get("/api/profissionais/")
        item = resposta.data["results"][0]
        self.assertEqual(set(item.keys()), self.CAMPOS_ESPERADOS_PROFISSIONAL)
```

**Matriz de rastreabilidade (a manter atualizada conforme os testes forem implementados):**

| SDD de origem | Critério | Pasta | Arquivo |
|---|---|---|---|
| SDD-03 | CA-01 a CA-09 | `tests/profissionais/` | `test_crud.py` / `test_erros.py` |
| SDD-03 | CA-10 a CA-16 | `tests/consultas/` | `test_crud.py` / `test_erros.py` |
| SDD-03 (extensões) | CA-17 a CA-20 | `tests/consultas/` | `test_refinamentos.py` |
| SDD-04 | CA-01 a CA-13 | `tests/seguranca/` | `test_autenticacao.py` / `test_rate_limiting.py` |
| SDD-04 | CA-14, CA-15 | `tests/seguranca/` | `test_health_check.py` (endpoints públicos, sem herdar de `APITestCaseAutenticado`) |
| SDD-04 | CA-16 | *(fora do escopo de `APITestCase`)* | validado via `QA-01-SMOKE-LACREI.md` — formato JSON dos logs é responsabilidade de infraestrutura/observabilidade, mais eficaz de checar contra o container real do que mockando o `StreamHandler` |
| SDD-05 (integração) | CA-04 | `tests/integracao/` | `test_fluxo_profissional_consulta.py` |
| SDD-05 (regressão) | CA-05 | `tests/regressao/` | `test_regressao.py` |
| SDD-05 (contrato) | CA-06, CA-07 | `tests/contrato/` | `test_contrato_profissionais.py` / `test_contrato_erros.py` |

---

## Checklist de implementação

- [ ] Estrutura de pastas de teste criada exatamente conforme a referência de implementação
- [ ] `tests/base.py` com `APITestCaseAutenticado` criado e usado por toda classe que testa endpoint protegido
- [ ] Todo teste referencia o CA de origem em docstring/comentário
- [ ] Nomes de teste derivados do critério (`test_<contexto>_<resultado_esperado>`)
- [ ] `tests/integracao/` cobre ao menos o ciclo de vida completo profissional↔consulta
- [ ] `tests/regressao/` documentado com causa raiz de cada bug real encontrado (não apenas o exemplo hipotético)
- [ ] `tests/contrato/` cobre o shape de resposta de sucesso e de erro
- [ ] Nenhum teste usa `Profissional.objects.all().delete()` ou limpeza manual — isolamento via banco de teste do Django
- [ ] `python manage.py test` roda a suíte inteira sem falha e sem teste `skipped` injustificado
- [ ] Matriz de rastreabilidade atualizada à medida que testes reais (não hipotéticos) forem adicionados
