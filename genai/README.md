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

Os testes não iniciam servidor nem fazem chamadas de rede:

```powershell
python -m pytest
```
