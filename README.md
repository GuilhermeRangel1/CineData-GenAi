# CineData GenAI

O CineData reúne um catálogo de filmes com recursos sociais em React e FastAPI
e um módulo GenAI independente para consultar a camada Gold em linguagem
natural. O chatbot envia perguntas ao serviço GenAI; as consultas SQL são
somente leitura e usam o Gold diretamente.

## Requisitos

- Docker Desktop com Docker Compose v2.
- Git e Git LFS para obter o banco Gold versionado.
- Chave Gemini configurada em `genai/.env` para perguntas analíticas do chatbot.
  Sem a chave, a aplicação e o catálogo iniciam e perguntas sobre como usar o
  CineData continuam disponíveis pelo guia local; perguntas analíticas retornam
  erro de configuração do provedor.

## Clonar e iniciar

Instale Git LFS antes de clonar para que o arquivo Gold seja baixado junto do
repositório. Depois, na raiz do projeto:

```powershell
git lfs install
git clone <URL_DO_REPOSITORIO>
cd CineData-GenAi
git lfs pull
Copy-Item genai/.env.example genai/.env
```

Edite `genai/.env` e preencha `GENAI_GEMINI_API_KEY`. Esse arquivo é local,
ignorado pelo Git e não deve ser compartilhado. A chave nunca é enviada ao
navegador. O modelo pode ser alterado por `GENAI_GEMINI_MODEL`.

Inicie todos os serviços com:

```powershell
docker compose up
```

O Compose constrói frontend, backend existente, inicializador de dados e
serviço GenAI a partir do código antes de iniciar os contêineres. O build usa o
cache do Docker quando possível. Não é necessário acrescentar `--build`. Na
primeira execução, o backend aplica migrações e sincroniza o catálogo Gold; essa
etapa pode levar alguns minutos.

| Serviço | Endereço local |
| --- | --- |
| CineData | http://localhost:8080 |
| API CineData | http://localhost:8000 |
| API GenAI | http://localhost:8001 |
| Saúde GenAI | http://localhost:8001/health |

Para encerrar, use `Ctrl+C`; para iniciar em segundo plano, use
`docker compose up -d`. Os dados locais persistem em `data/`.

## Bancos de dados

`data/cinerocket.db` é a camada Gold analítica de aproximadamente 581 MB,
versionada via Git LFS e montada como somente leitura nos serviços. O manifesto
`data/cinerocket.db.sha256` valida o tamanho do arquivo na inicialização. Se um
clone tiver apenas um arquivo pointer LFS, rode `git lfs pull` antes do Compose.

O banco operacional da aplicação fica em `data/rocketlab.db`, é criado pelo
Compose e ignorado pelo Git. O backend sincroniza os dados Gold para ele e
preserva contas, listas, avaliações e recursos sociais. Não coloque bancos
operacionais, arquivos `.env` ou ZIPs de dados no repositório. Mais detalhes em
[docs/database.md](docs/database.md).

## Chatbot e perguntas analíticas

O módulo em `genai/` é uma API FastAPI separada. Usa Gemini com tool calling e
um executor SQL que abre o Gold SQLite em modo somente leitura, permite apenas
consultas seguras às tabelas autorizadas e devolve resposta em português com
metadados e evidências tabulares. A chave fica apenas no ambiente do serviço.

O agente cobre as perguntas de finanças, popularidade e notas, elenco e equipe,
gêneros e produtoras e avaliações de usuários. Regras, esquema e perguntas de
referência estão em `genai/` e `docs/genai/`. O chatbot reutiliza a interface
CineData e está acessível pelo botão “Chatbot”. Cada pergunta é independente;
o histórico apresentado na tela não é enviado como memória ao modelo.

## Testes de desenvolvimento

As avaliações automatizadas não chamam o provedor e não gastam cota:
Execute cada sequência em um terminal novo, sempre a partir da raiz do projeto.

```powershell
cd frontend
npm ci
npm test
npm run build
```

```powershell
cd genai
python -m pip install -e ".[dev]"
python -m pytest
```

Use chamadas reais ao modelo de forma controlada. Tool calling pode usar mais
de uma requisição por pergunta; o limite informado para o plano gratuito é 50
requisições diárias. Durante desenvolvimento, limite as verificações manuais a
poucas chamadas e evite retries ou avaliações em lote com o modelo real.

## Documentação

- [Plano de execução](docs/.ruler/TODO.md)
- [Tooling e convenções](docs/.ruler/tooling.md)
- [Esquema e regras do Gold](genai/gold-schema.md)
- [Regras de métricas](genai/metric-rules.md)
- [Consultas de referência](genai/reference-queries.sql)
- [Banco de dados e sincronização](docs/database.md)
