# Módulo GenAI

Módulo FastAPI isolado do CineData. Neste checkpoint ele contém somente o
esqueleto executável e o health check. O acesso ao Gold, a ferramenta SQL, o
agente e a integração com provedor serão adicionados em blocos posteriores.

## Execução local

Na pasta `genai/`, crie um ambiente Python 3.11 ou superior, instale as
dependências do projeto e inicie:

```powershell
python -m pip install -e ".[dev]"
python -m uvicorn app.main:app --reload
```

O health check fica disponível em `http://127.0.0.1:8000/health`.

O caminho do Gold é configurável por `GENAI_GOLD_DATABASE_PATH`; por padrão,
quando o comando é executado dentro de `genai/`, ele aponta para
`../data/cinerocket.db`. A camada de dados abre o arquivo com SQLite `mode=ro`,
valida o objeto Git LFS, a integridade e as tabelas esperadas. Ela ainda não é
usada por um endpoint de pergunta neste checkpoint.

As consultas passam por `sqlglot` antes da execução. O executor aceita uma
única instrução `SELECT`, restringe as tabelas Gold, aplica limite de linhas e
tempo e mantém uma autorização SQLite read-only como segunda barreira. DML,
DDL, múltiplas instruções, acesso externo e funções de arquivo são rejeitados.

Os testes não iniciam servidor nem fazem chamadas de rede:

```powershell
python -m pytest
```
