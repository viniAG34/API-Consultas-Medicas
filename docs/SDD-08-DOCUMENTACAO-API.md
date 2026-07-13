# SDD-08 — Documentação da API (Swagger/Redoc)
> Leia SDD-03 e SDD-04 antes de implementar.
> Última atualização: 2026-07-09
> Status: bônus opcional — implementar apenas se os itens obrigatórios (SDD-01 a SDD-07) estiverem concluídos.

---

## Responsabilidade

Gerar documentação interativa e navegável da API (OpenAPI/Swagger e Redoc) a partir dos serializers e views já existentes, sem exigir escrita manual de spec — usando introspecção automática do DRF via `drf-spectacular`.

**Não faz:** não define novos endpoints, não altera comportamento de negócio. Apenas expõe o contrato da API já implementada (SDD-03, SDD-04) de forma navegável para quem for consumi-la.

---

## Regras de negócio

- RN-01: A documentação é gerada automaticamente a partir dos serializers e viewsets existentes (introspecção) — nunca escrita manualmente em YAML solto, para evitar divergência entre spec e implementação real.
- RN-02: O schema OpenAPI fica disponível em `/api/schema/`, o Swagger UI em `/api/docs/`, e o Redoc em `/api/redoc/`.
- RN-03: A documentação reflete a exigência de autenticação (JWT) em cada endpoint — quem acessa o Swagger UI consegue autenticar diretamente na interface para testar chamadas reais.
- RN-04: Endpoints de token (`/api/token/`, `/api/token/refresh/`) aparecem documentados junto aos demais, já que fazem parte do fluxo de uso real da API.
- RN-05: A documentação é acessível em todos os ambientes (dev, staging, produção) — não é uma feature exclusiva de desenvolvimento, pois o objetivo do item bônus é facilitar a avaliação por terceiros.
- RN-06: Descrições de endpoints e campos usam os nomes em português já definidos nos serializers — a documentação não traduz nem reformula a nomenclatura do projeto.

---

## Critérios de aceite

- CA-01: Dado o servidor rodando
         Quando acessado `GET /api/schema/`
         Então retorna o schema OpenAPI 3.0 válido em formato YAML/JSON

- CA-02: Dado o servidor rodando
         Quando acessado `GET /api/docs/`
         Então a interface Swagger UI carrega, listando todos os endpoints de `Profissional`, `Consulta` e autenticação

- CA-03: Dado o servidor rodando
         Quando acessado `GET /api/redoc/`
         Então a interface Redoc carrega como alternativa de visualização ao Swagger

- CA-04: Dado o Swagger UI aberto
         Quando o usuário insere um token JWT válido via botão "Authorize"
         Então consegue executar requisições autenticadas diretamente pela interface (ex: `GET /api/profissionais/`) e ver a resposta real

- CA-05: Dado um endpoint que exige autenticação (SDD-04)
         Quando visualizado no Swagger/Redoc
         Então a documentação indica claramente que autenticação é necessária (ícone de cadeado ou seção de segurança)

- CA-06: Dado um serializer com validação customizada (ex: `ProfissionalSerializer.validate()`, RN-08 do SDD-02)
         Quando visualizado no Swagger
         Então os campos `email`/`telefone` aparecem documentados, mesmo que a regra combinada não seja expressável visualmente no schema (limitação aceita do OpenAPI padrão)

---

## Erros e exceções

- Guard A (crítico — propaga): nenhum aplicável — geração de schema é introspecção read-only, não deve falhar em runtime normal; se falhar, é erro de configuração a ser corrigido antes do deploy, não um caso de erro de usuário
- Guard B (fallback): nenhum aplicável nesta camada
- Guard C (silencioso): campo/endpoint sem `docstring` ou `help_text` explícito → aparece na documentação sem descrição detalhada, mas não quebra a geração do schema

---

## Referência de implementação

**Dependência adicional no `pyproject.toml`:**
- `drf-spectacular`

**`settings/base.py`:**
```python
INSTALLED_APPS += ["drf_spectacular"]

REST_FRAMEWORK["DEFAULT_SCHEMA_CLASS"] = "drf_spectacular.openapi.AutoSchema"

SPECTACULAR_SETTINGS = {
    "TITLE": "API de Gerenciamento de Consultas Médicas — Lacrei Saúde",
    "DESCRIPTION": "API RESTful para cadastro de profissionais da saúde e gerenciamento de consultas.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
}
```

**`config/urls.py`:**
```python
from rest_framework.permissions import AllowAny
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView,
)


class SpectacularAPIViewPublica(SpectacularAPIView):
    """Pública por design (SDD-04, RN-15) — documentação deve ser navegável sem token."""
    permission_classes = [AllowAny]


class SpectacularSwaggerViewPublica(SpectacularSwaggerView):
    permission_classes = [AllowAny]


class SpectacularRedocViewPublica(SpectacularRedocView):
    permission_classes = [AllowAny]


urlpatterns += [
    path("api/schema/", SpectacularAPIViewPublica.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerViewPublica.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocViewPublica.as_view(url_name="schema"), name="redoc"),
]
```

> **Nota:** sem o `permission_classes = [AllowAny]` explícito acima, essas views herdariam o
> `IsAuthenticated` global definido no SDD-04 — um avaliador sem token não conseguiria nem
> abrir a documentação para descobrir como se autenticar (ver SDD-04, RN-15).

**Descrições nos serializers (RN-06 — exemplo):**
```python
class ProfissionalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Profissional
        fields = [...]
        read_only_fields = ["id", "criado_em", "atualizado_em"]

    email = serializers.EmailField(
        required=False,
        help_text="Email de contato. Obrigatório se telefone não for informado.",
    )
    telefone = serializers.CharField(
        required=False,
        help_text="Telefone de contato. Obrigatório se email não for informado.",
    )
```

---

## Checklist de implementação

- [ ] `drf-spectacular` instalado e configurado como `DEFAULT_SCHEMA_CLASS`
- [ ] `/api/schema/`, `/api/docs/` e `/api/redoc/` acessíveis
- [ ] Views de documentação com `permission_classes = [AllowAny]` explícito (SDD-04, RN-15) — sem isso, ficam inacessíveis a quem não tem token
- [ ] Autenticação JWT testável diretamente pelo Swagger UI (botão "Authorize")
- [ ] `help_text` adicionado nos campos com validação combinada não óbvia (`email`/`telefone`)
- [ ] Título e descrição da API preenchidos em `SPECTACULAR_SETTINGS`
- [ ] Link para `/api/docs/` incluído no README (SDD-09)
