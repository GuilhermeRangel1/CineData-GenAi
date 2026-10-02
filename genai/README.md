# Módulo GenAI

Módulo FastAPI isolado do CineData. Ele contém acesso read-only ao Gold, uma
ferramenta SQL protegida, a orquestração interna do agente, um adaptador
configurável para o Gemini e a rota HTTP de perguntas.

## Execução local

Na pasta `genai/`, crie um ambiente Python 3.11 ou superior. Para usar o
provedor, copie `.env.example` para `.env` e configure
`GENAI_GEMINI_API_KEY`. Instale as dependências e inicie:

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

O health check fica disponível em `http://127.0.0.1:8000/health`.
Perguntas são enviadas para `POST http://127.0.0.1:8000/api/v1/questions` com o
corpo `{"question": "Quantos filmes existem?"}`. A resposta contém o texto
gerado, as linhas retornadas pela consulta, o indicador de truncamento e a
quantidade de chamadas de ferramenta.

O caminho do Gold é configurável por `GENAI_GOLD_DATABASE_PATH`; por padrão,
quando o comando é executado dentro de `genai/`, ele aponta para
`../data/cinerocket.db`. A camada de dados abre o arquivo com SQLite `mode=ro`,
valida o objeto Git LFS, a integridade e as tabelas esperadas. A rota de
perguntas usa essa camada por meio do agente e nunca expõe a chave do provedor
ao navegador.

As consultas passam por `sqlglot` antes da execução. O executor aceita uma
única instrução `SELECT`, restringe as tabelas Gold, aplica limite de linhas e
tempo e mantém uma autorização SQLite read-only como segunda barreira. DML,
DDL, múltiplas instruções, acesso externo e funções de arquivo são rejeitados.
Consultas que atravessam tabelas de relação ou avaliações recebem orçamento de
15 segundos; a agregação de dupla ator-diretor recebe 45 segundos. As demais
permanecem limitadas a 5 segundos.

Os testes não iniciam servidor nem fazem chamadas de rede. Para configurações
sem provedor, um cliente simulado mantém os testes determinísticos:

```powershell
python -m pytest
```

O adaptador lê `GENAI_GEMINI_API_KEY` do `.env` e usa
`GENAI_GEMINI_MODEL` ou `gemini-3.5-flash-lite` por padrão. A suíte de testes injeta
um cliente simulado; ela nunca consome a cota do provedor.

As perguntas obrigatórias estão catalogadas em
[`docs/genai/evaluation-cases.md`](../docs/genai/evaluation-cases.md), com os
identificadores Q01–Q14 e as colunas esperadas para as avaliações locais.
Todos os casos Q01–Q14 carregam no contexto do agente a métrica, unidade,
período, população válida e limitações que devem aparecer na resposta em
português.
Para esses casos, o agente rejeita uma resposta final sem os rótulos semânticos
obrigatórios. Quando o modelo sinaliza `CLARIFY:`, a API retorna esclarecimento
com status 422 sem executar uma consulta.
## Execução com Docker Compose

Na raiz do repositório, copie `genai/.env.example` para `genai/.env` e configure
`GENAI_GEMINI_API_KEY`. Esse arquivo é local e não deve ser versionado. Sem a
chave, os demais serviços iniciam, mas perguntas ao agente retornam erro de
configuração do provedor.

Execute na raiz:

```powershell
docker compose up
```

O Compose constrói os serviços a partir do código e os inicia. O GenAI fica em
`http://localhost:8001`; o frontend em `http://localhost:8080`. O arquivo Gold
do projeto é montado em modo somente leitura. Ao iniciar, o GenAI verifica seu
SHA-256 e mantém uma cópia em um volume local do Docker para acelerar as
consultas. Novas versões do Gold atualizam essa cópia automaticamente.
