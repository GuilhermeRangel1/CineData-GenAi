# Módulo GenAI

Serviço FastAPI independente que sustenta o chatbot analítico do CineData. O
serviço recebe perguntas em português, diferencia orientação sobre a plataforma
de análise do catálogo e mantém o acesso ao Gold SQLite exclusivamente em modo
leitura.

## Fluxo

```text
pergunta → guardrails → Gemini com run_sql → validação SQL → Gold read-only
         → resposta estruturada → tabela, gráfico e insights no frontend
```

Perguntas sobre catálogo, listas, comunidades ou mapa de gostos usam o guia
local em `docs/platform-guide.md` e não consomem cota Gemini. Perguntas sobre
filmes podem usar a busca local por títulos e sinopses; quando há uma métrica,
ela é consultada no Gold após a validação SQL.

A chave Gemini habilita todas as consultas a dados, inclusive as que usam SQL
preparado ou busca local. Sua presença não significa que toda resposta faça
uma chamada ao modelo.

Nas 14 perguntas canônicas da Ajuda, o Gemini recebe o esquema necessário e as
regras da métrica para gerar o SQL. Q04, Q05, Q06, Q07, Q08, Q09, Q10, Q11 e
Q14 têm consultas de referência: o serviço compara as linhas retornadas e usa
a referência se a geração ou a conferência falhar. A referência começa em
paralelo à chamada do modelo. Os insights podem usar uma chamada textual ao
Gemini sobre os resultados já validados; a série anual da nota IMDb mantém um
resumo local. Variações reconhecidas podem usar SQL preparado; perguntas
analíticas livres dependem do modelo.

## Segurança e disponibilidade

- somente uma instrução `SELECT` sobre tabelas e colunas autorizadas;
- `sqlglot`, limite de linhas, timeout e SQLite `mode=ro` protegem a execução;
- guardrails rejeitam SQL enviado pela pessoa, pedidos fora de escopo e
  tentativas de alterar as regras do agente;
- o modelo principal pode recorrer uma vez ao modelo de fallback para falhas
  temporárias de conexão, cota, timeout ou resposta 5xx;
- perguntas livres equivalentes ficam em cache por cinco minutos, isoladas
  por conversa e contexto; as 14 perguntas completas da Ajuda compartilham
  respostas públicas por até uma hora, sempre considerando a revisão do Gold
  e a versão das regras;
- o serviço nunca recebe token de sessão, senha ou identificador da conta.

## API

`GET /health` retorna o estado do processo. `GET /api/v1/capabilities` informa
se as consultas analíticas estão disponíveis, sem expor a chave.
`POST /api/v1/questions` recebe:

```json
{
  "question": "Quais são os 5 filmes com maior receita em BRL?",
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

`context` é opcional, tem no máximo três resumos da conversa atual e permite
continuações como “e em 2020?”. `conversation_id` é um identificador local do
frontend usado para separar o cache das perguntas livres; Q01–Q14 canônicas
compartilham a resposta pública por até uma hora. O histórico
persistente pertence ao backend principal. O contrato completo está em
[docs/genai/api-contract.md](../docs/genai/api-contract.md).

Uma resposta de sucesso contém `answer`, `rows`, `insights` e `metadata`.
`metadata.source` informa se a evidência veio do Gold, do guia da plataforma,
da busca semântica ou de uma combinação dessas fontes. Para consultas
obrigatórias, os metadados incluem métrica, unidade, período, população e
limitações.

## Execução local

Na raiz do repositório, obtenha o Gold com `git lfs pull`. Depois, na pasta
`genai/`, instale as dependências e execute:

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload --port 8001
```

O health check fica em `http://127.0.0.1:8001/health` e a API em
`http://127.0.0.1:8001/api/v1/questions`.

Para consultar dados de filmes, copie `.env.example` para `.env` e preencha
`GENAI_GEMINI_API_KEY`. A chave é exigida também para consultas SQL preparadas
e busca em sinopses; a orientação sobre a plataforma continua disponível sem
ela. `GENAI_GEMINI_MODEL` e `GENAI_GEMINI_FALLBACK_MODEL` definem os modelos
principal e alternativo.

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
