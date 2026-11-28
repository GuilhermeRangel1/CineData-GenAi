# Módulo GenAI

Serviço FastAPI independente que sustenta o chatbot analítico do CineData. O
serviço recebe perguntas em português, diferencia orientação sobre a plataforma
de análise do catálogo e mantém o acesso ao Gold SQLite exclusivamente em modo
leitura.

## Fluxo

```text
pergunta → guardrails → provedor com run_sql → validação SQL → Gold read-only
         → resposta estruturada → tabela, gráfico e insights no frontend
```

Perguntas sobre catálogo, listas, comunidades ou mapa de gostos usam o guia
local em `docs/platform-guide.md`. Perguntas sobre filmes podem usar a busca
nas sinopses. Quando a busca precisa ampliar os termos, o provedor recebe
até dois termos da pergunta e a seleção continua local. A ficha de um filme
também pode usar o provedor para resumir uma sinopse em português.

A configuração de ao menos um provedor habilita todas as consultas a dados,
inclusive SQL preparado ou busca local. Isso não significa que toda resposta
faça uma chamada ao modelo. Gemini permanece como rota principal padrão;
Groq e OpenRouter são alternativas independentes.

## Provedores

Defina `GENAI_PROVIDER_ORDER=gemini,groq,openrouter` para usar essa cadeia ou
uma lista reduzida para isolar um provedor. Gemini usa as variáveis existentes.
Groq exige `GENAI_GROQ_API_KEY` e `GENAI_GROQ_MODEL`; OpenRouter exige
`GENAI_OPENROUTER_API_KEY` e `GENAI_OPENROUTER_MODEL`. Modelos alternativos não
são escolhidos automaticamente. Confira suporte a ferramentas, cota e preço
antes de configurar. Sem chave ou modelo, a rota é ignorada.

Limites padrão: `GENAI_PROVIDER_TIMEOUT_SECONDS=12`,
`GENAI_PROVIDER_BUDGET_SECONDS=40` e `GENAI_PROVIDER_COOLDOWN_SECONDS=60`.
Para chamadas analíticas, o Gemini tem limite padrão de 20 segundos e o
OpenRouter de 36 segundos, ambos sujeitos ao orçamento total da pergunta.
Configure esses limites com `GENAI_GEMINI_ANALYTICAL_TIMEOUT_SECONDS` e
`GENAI_OPENROUTER_ANALYTICAL_TIMEOUT_SECONDS`.
O timeout cancela a chamada; o orçamento soma o tempo de inferência da pergunta
e pausa durante SQL. Uma rota com falha transitória entra em cooldown; apenas
uma tentativa de recuperação roda por vez. Chaves rejeitadas ficam desativadas
até reiniciar o processo. O provedor que respondeu passa a ser preferido nos
turnos restantes daquela pergunta; outras perguntas mantêm sua própria ordem.

`GET /api/v1/capabilities` indica configuração, sem sondar a saúde externa.
Falha total sem cache retorna `provider_unavailable` (HTTP 503), preservando o
guia local. As recuperações SQL de referência já existentes continuam ativas
nas perguntas canônicas. Veja o [roteiro de testes reais](../docs/genai/provider-validation.md).

Protocolos: [Groq](https://console.groq.com/docs/openai),
[OpenRouter](https://openrouter.ai/docs/api/reference/overview),
[Google GenAI](https://googleapis.github.io/python-genai/).

A suíte cobre 50 perguntas oficiais. O provedor recebe o esquema e as regras
da métrica quando a consulta exige SQL gerado. Nos casos cobertos, o serviço
compara o resultado com uma consulta de referência e pode usá-la para recuperar
falhas. Consultas reconhecidas também podem usar SQL local. As respostas podem
incluir insights calculados sobre os resultados validados.

## Segurança e disponibilidade

- uma única instrução `SELECT` ou `UNION` sobre tabelas e colunas autorizadas;
- `sqlglot`, limite de linhas, timeout e SQLite `mode=ro` protegem a execução;
- guardrails rejeitam SQL enviado pela pessoa, pedidos fora de escopo e
  tentativas de alterar as regras do agente;
- o modelo principal pode recorrer uma vez ao modelo de fallback para falhas
  temporárias de conexão, cota, timeout ou resposta 5xx;
- perguntas livres equivalentes ficam em cache por cinco minutos, isoladas
  por conversa e contexto; as formulações canônicas Q01–Q14 compartilham
  respostas públicas por até uma hora, sempre considerando a revisão do Gold
  e a versão das regras;
- o serviço nunca recebe token de sessão, senha ou identificador da conta.

## API

`GET /health` retorna o estado do processo. `GET /api/v1/capabilities` informa
se as consultas analíticas estão disponíveis, sem expor a chave.
`POST /api/v1/questions` recebe:

```json
{
  "question": "E em 2020?",
  "context": [
    {
      "question": "Qual produtora teve maior lucro?",
      "metric": "lucro total por produtora",
      "unit": "BRL"
    }
  ],
  "conversation_id": "identificador-local-da-conversa"
}
```

`context` é opcional, tem no máximo dez resumos da conversa atual e permite
continuações como “e em 2020?”. `conversation_id` é um identificador local do
frontend usado para separar o cache das perguntas livres; Q01–Q14 canônicas
compartilham a resposta pública por até uma hora. O histórico
persistente pertence ao backend principal. O contrato completo está em
[docs/genai/api-contract.md](../docs/genai/api-contract.md).

Uma resposta de sucesso contém `answer`, `rows`, `insights` e `metadata`.
`metadata.source` informa se a evidência veio do Gold, do guia da plataforma,
da busca semântica ou de uma combinação dessas fontes. Os metadados podem
incluir métrica, unidade, período, população e limitações conforme o caso.

## Execução local

Na raiz do repositório, obtenha o Gold com `git lfs pull`. Depois, na pasta
`genai/`, instale as dependências e execute:

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8001
```

O health check fica em `http://127.0.0.1:8001/health` e a API em
`http://127.0.0.1:8001/api/v1/questions`.

Para consultar dados de filmes, copie `.env.example` para `.env` e configure pelo menos um dos provedores descritos acima. Para Gemini, use
`GENAI_GEMINI_API_KEY` e, se precisar ajustar os modelos,
`GENAI_GEMINI_MODEL` e `GENAI_GEMINI_FALLBACK_MODEL`. O token opcional
`GENAI_TMDB_API_TOKEN` ajuda na resolução de títulos e na busca de sinopses.

## Docker Compose e testes

Na raiz, `docker compose up` constrói o serviço e o publica em
`http://localhost:8001`. O Compose verifica o Gold, mantém uma cópia local em
um volume para reduzir latência e atualiza a cópia quando a revisão do arquivo
muda.

Os testes usam modelos simulados e não fazem chamadas à Gemini:

```powershell
python -m pytest
python -m ruff check .
```

As perguntas obrigatórias, regras e SQL de referência estão em
[docs/genai/](../docs/genai/). O avaliador compara valores e colunas relevantes
com o Gold, sem exigir que o SQL gerado seja textual e exatamente igual ao SQL
de referência.
