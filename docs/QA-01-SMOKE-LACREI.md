# QA-01 — Smoke Test e Infraestrutura (Lacrei Saúde)

> Execute este QA logo após implementar os SDD-01 a SDD-04 (setup, modelagem, CRUD e
> segurança) — antes de escrever os testes formais do SDD-05. Se falhar aqui, corrija antes
> de seguir: os itens abaixo validam contra o **container real rodando**, não contra
> `APITestCase` — é a camada que pega bugs de configuração que testes unitários não pegam
> (ex: uma view protegida sem querer, uma variável de ambiente esquecida).

---

## Objetivo

Verificar que o sistema sobe, responde e está estruturalmente correto — incluindo validar
explicitamente as exceções de autenticação (`/health/`, `/api/token/`, docs) que a auditoria
dos SDDs identificou como ponto crítico.

---

## Pré-requisitos

- `.env` preenchido com valores reais (`SECRET_KEY`, `POSTGRES_*`, etc.)
- Docker e Docker Compose instalados
- Migrations já aplicadas (`makemigrations` + `migrate` rodados ao menos uma vez)

---

## 1. Build Docker

```bash
docker build -t lacrei-api:qa .
echo "Exit code: $?"

docker image inspect lacrei-api:qa | python3 -c "
import sys, json
data = json.load(sys.stdin)[0]
print('Tamanho:', round(data['Size'] / 1024 / 1024), 'MB')
print('Criado em:', data['Created'][:19])
"
```

**Critério:** build sem erros.

---

## 2. Subir os containers

```bash
docker-compose up -d --build
sleep 5
docker-compose logs web --tail 30
```

**Critério:** logs mostram o boot do Gunicorn, `migrate`/`collectstatic` executados pelo
entrypoint (SDD-01, RN-12), sem `Traceback` ou `CRITICAL`.

---

## 3. Healthcheck público (sem token) — valida SDD-04, RN-15

```bash
RESULTADO=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/)
[ "$RESULTADO" = "200" ] && echo "✓ /health/ acessível sem token" \
  || echo "✗ FALHA: /health/ retornou $RESULTADO — provável IsAuthenticated global sem exceção (ver SDD-04, RN-15)"

curl -s http://localhost:8000/health/ | python3 -m json.tool
```

**Critério:** `200`, sem header `Authorization`. Se retornar `401`, a exceção de `AllowAny`
não foi aplicada na view — **isso bloquearia o healthcheck do deploy inteiro (SDD-07)**.

---

## 4. Obtenção de token sem autenticação prévia — valida o "loop impossível" (SDD-04, RN-15)

```bash
# Criar usuário de teste antes, se ainda não existir:
# docker-compose exec web python manage.py createsuperuser

RESULTADO=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "usuario_qa", "password": "senha_qa_conhecida"}')

[ "$RESULTADO" = "200" ] && echo "✓ /api/token/ acessível sem autenticação prévia" \
  || echo "✗ FALHA: /api/token/ retornou $RESULTADO — sem AllowAny, ninguém consegue logar (SDD-04, RN-15)"

# Guardar o token para os próximos passos
export TOKEN=$(curl -s -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "usuario_qa", "password": "senha_qa_conhecida"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('access',''))")

echo "Token obtido: ${TOKEN:0:20}..."
```

**Critério:** `200` com `access` e `refresh` no corpo. Este é o teste mais importante do QA —
sem ele passar, nenhuma outra rota autenticada é alcançável.

---

## 5. Rota protegida — sem token vs. com token

```bash
# Sem token → 401
RESULTADO=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/profissionais/)
[ "$RESULTADO" = "401" ] && echo "✓ Rota protegida sem token → 401" \
  || echo "✗ Esperado 401, recebido $RESULTADO"

# Com token → 200
RESULTADO=$(curl -s -o /dev/null -w "%{http_code}" \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/profissionais/)
[ "$RESULTADO" = "200" ] && echo "✓ Rota protegida com token válido → 200" \
  || echo "✗ Esperado 200, recebido $RESULTADO"
```

---

## 6. Documentação da API pública (se SDD-08 implementado) — valida SDD-08

```bash
for rota in "api/schema/" "api/docs/" "api/redoc/"; do
  RESULTADO=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:8000/$rota")
  [ "$RESULTADO" = "200" ] && echo "✓ /$rota acessível sem token" \
    || echo "✗ FALHA: /$rota retornou $RESULTADO — falta AllowAny explícito (SDD-08)"
done
```

**Critério:** as três rotas retornam `200` sem header `Authorization`.

---

## 7. Verificar logs estruturados em JSON

```bash
docker-compose logs web --tail 30 --no-color | python3 -c "
import sys, json
linhas = [l for l in sys.stdin.readlines() if l.strip()]
erros = []
for i, linha in enumerate(linhas, 1):
    try:
        obj = json.loads(linha.split(maxsplit=0)[-1] if False else linha)
        for campo in ('ts', 'nivel', 'modulo', 'mensagem'):
            assert campo in obj, f'campo {campo} ausente'
    except json.JSONDecodeError:
        erros.append(f'Linha {i} não é JSON válido: {linha[:80].strip()}')
    except AssertionError as e:
        erros.append(f'Linha {i}: {e}')

if erros:
    print('✗ Erros encontrados (algumas linhas podem ser do Gunicorn/Django, não da app):')
    for e in erros[:10]:
        print(f'  {e}')
else:
    print(f'✓ {len(linhas)} linhas — todas JSON válidas com campos padrão')
"
```

**Critério:** logs emitidos pela aplicação (via `apps.core.logging`) são JSON de uma linha
com `ts`, `nivel`, `modulo`, `mensagem`. Linhas de boot do Gunicorn/Django podem não seguir o
padrão — foco é nos logs de acesso/erro da aplicação (SDD-04).

---

## 8. Token não aparece nos logs

```bash
docker-compose logs web --tail 100 --no-color | grep -c "$TOKEN" | xargs -I{} sh -c \
  'test {} -eq 0 && echo "✓ Token não aparece nos logs" || echo "✗ FALHA: token encontrado nos logs"'
```

---

## 9. Rate limiting no login (SDD-04, RN-12/RN-13)

```bash
python3 << 'EOF'
import urllib.request, json

url = "http://localhost:8000/api/token/"
payload = json.dumps({"username": "usuario_qa", "password": "senha_errada"}).encode()
headers = {"Content-Type": "application/json"}

resultados = []
for i in range(7):
    req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            resultados.append(r.status)
    except urllib.error.HTTPError as e:
        resultados.append(e.code)

print(f"Tentativas: {resultados}")
assert 429 in resultados[4:], "esperado 429 entre a 5ª e 7ª tentativa (TAXA_THROTTLE_LOGIN=5/minuto)"
print("✓ Rate limiting de login ativo")
EOF
```

---

## 10. Suíte de testes dentro do container

```bash
docker-compose exec web python manage.py test
```

**Critério:** todos os testes passam (SDD-05), incluindo `tests/seguranca/test_health_check.py`
e `tests/integracao/`.

---

## 11. Limpeza

```bash
docker-compose down
```

---

## Checklist de Aprovação

- [ ] Build Docker sem erros
- [ ] Containers sobem sem `Traceback`/`CRITICAL` nos logs
- [ ] `/health/` retorna 200 **sem token** (SDD-04, RN-15)
- [ ] `/api/token/` retorna 200 **sem autenticação prévia** (SDD-04, RN-15) — item mais crítico
- [ ] Rota protegida: 401 sem token, 200 com token válido
- [ ] `/api/docs/`, `/api/schema/`, `/api/redoc/` acessíveis sem token (se SDD-08 implementado)
- [ ] Logs da aplicação em JSON estruturado com campos padrão
- [ ] Token não aparece nos logs
- [ ] Rate limiting de login ativa 429 após 5 tentativas
- [ ] `python manage.py test` passa dentro do container
