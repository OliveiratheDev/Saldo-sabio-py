# 💸 Bot Financeiro — Agente de Finanças Pessoais

Agente financeiro inteligente via WhatsApp, refatorado de Java para Python com FastAPI. Registre gastos por mensagem de texto, receba insights automáticos e controle suas finanças sem sair do celular.

---

## 🔄 Por que migramos de Java para Python?

O projeto foi originalmente desenvolvido em Java e passou por uma refatoração completa para Python. Os principais benefícios dessa migração foram:

- **Menos código, mais produtividade** — Python elimina boilerplate. O que em Java exigia dezenas de linhas, em Python se resolve em poucas.
- **Ecossistema de IA e ML superior** — bibliotecas como OpenAI SDK, LangChain e outras integram nativamente com Python, sem adaptadores ou wrappers.
- **FastAPI em vez de Spring Boot** — startup instantâneo, tipagem com Pydantic, documentação automática com Swagger, e performance assíncrona nativa.
- **Facilidade de deploy** — um simples `pip install -r requirements.txt` substitui configurações complexas de Maven/Gradle.
- **Iteração mais rápida** — ideal para projetos com IA onde o código muda constantemente durante experimentos.

---

## ✨ Funcionalidades

- Registro de gastos por mensagem de WhatsApp (`"25,50 café"`)
- Isolamento por usuário — cada número vê apenas seus próprios dados
- Autenticação por `X-API-Key` em todas as rotas protegidas
- Insights automáticos: total do mês, categorias, resumo
- Chat agent com contexto financeiro do usuário
- Suíte de testes hermética — sem chamadas externas, 14 testes passando

---

## 🚀 Como rodar

### Pré-requisitos

- Python 3.11+
- pip

### Instalação

```bash
git clone https://github.com/seu-usuario/bot-py.git
cd bot-py
pip install -r requirements.txt
```

### Configuração

Copie o arquivo de exemplo e preencha suas variáveis:

```bash
cp .env.example .env
```

Edite o `.env`:

```env
API_KEY=sua-chave-secreta
OPENAI_API_KEY=sua-chave-openai
DATABASE_URL=sqlite:///./gastos.db
```

### Rodando o servidor

```bash
cd src
uvicorn main:app --reload
```

A API estará disponível em `http://localhost:8000` com documentação automática em `/docs`.

---

## 🧪 Testes

```bash
PYTHONPATH="src" API_KEY="test-key" python -m unittest src.test_services -v
```

Resultado esperado:

```
Ran 14 tests in 0.7s
OK
```

Os testes cobrem:
- Autenticação por `X-API-Key`
- Isolamento de dados entre usuários
- Proteção de rotas
- Webhook do WhatsApp
- Serviços de insights e chat

---

## 📡 Endpoints principais

| Método | Rota | Descrição |
|--------|------|-----------|
| `GET` | `/` | Health check público |
| `GET` | `/api/gastos` | Lista gastos do usuário |
| `POST` | `/api/gastos` | Cria um gasto |
| `DELETE` | `/api/gastos/{id}` | Remove um gasto |
| `POST` | `/api/whatsapp/webhook` | Recebe mensagens do WhatsApp |
| `GET` | `/api/insights` | Resumo financeiro do mês |

Todas as rotas (exceto `/`) exigem o header `X-API-Key` e `X-User-Id`.

---

## 🛠️ Stack

- **Python 3.11+**
- **FastAPI** — API REST assíncrona
- **SQLAlchemy** — ORM com suporte a SQLite e PostgreSQL
- **Pydantic** — validação de dados
- **OpenAI SDK** — agente de chat com contexto financeiro
- **Twilio / WhatsApp** — integração com webhook

---

## 📌 Próximos passos

- [ ] Frontend web (React/Vite)
- [ ] Autenticação por JWT para uso público
- [ ] Deploy em produção (Railway, Render ou VPS)
- [ ] Remoção da dependência de WhatsApp após migração para web

---

## ⚠️ Segurança

Nunca suba o arquivo `.env` para o repositório. Ele já está no `.gitignore`. Revogue qualquer chave que tenha sido exposta acidentalmente.
