# Tooling e convenções — CineData GenAI

O plano de trabalho vigente está em [`TODO.md`](TODO.md). Este guia registra a
arquitetura e os comandos usados para desenvolver e executar o CineData; não
substitui os contratos analíticos em `genai/`.

## Estrutura

```text
.
├── backend/                 # API CineData, autenticação e recursos sociais
├── frontend/                # React; chatbot consome a API GenAI por HTTP
├── genai/                   # serviço FastAPI Text-to-SQL independente
│   ├── app/                 # agente, provedor, API e executor SQL
│   ├── tests/               # testes com cliente de modelo simulado
│   ├── pyproject.toml       # dependências próprias
│   └── .env.example         # modelo de configuração local
├── data/cinerocket.db       # Gold via Git LFS; fonte somente leitura
├── data/rocketlab.db        # persistência operacional local, ignorada pelo Git
└── docker-compose.yml       # inicialização coordenada dos serviços
```

O backend existente preserva catálogo e funcionalidades sociais. O serviço
`genai` consulta o Gold diretamente e não depende do banco operacional. A chave
do provedor fica em `genai/.env`; o frontend não recebe esse segredo.

## Clone e execução Compose

Git LFS precisa estar instalado para baixar o objeto Gold durante o clone. Para
um checkout já criado sem o conteúdo LFS, execute `git lfs install` e
`git lfs pull` na raiz. O inicializador valida o tamanho/manifesto e as tabelas
Gold e falha com mensagem clara se recebeu somente o pointer LFS.

Copie `genai/.env.example` para `genai/.env` e preencha
`GENAI_GEMINI_API_KEY`. Esse segredo é opcional para iniciar os outros serviços;
sem ele, o endpoint GenAI informa que o provedor não está configurado.

Na raiz do projeto, use:

```powershell
docker compose up
```

Cada serviço define `pull_policy: build`, então `up` constrói as imagens do
checkout atual mesmo se já houver uma imagem local. O cache de camadas reduz os
builds seguintes. `docker compose up --build` também funciona, mas não é
necessário. Use `docker compose up -d` para executar em segundo plano e
`docker compose down` para parar e remover os contêineres/rede. A persistência
`./data` fica no projeto e não é removida por `down`.

Endereços locais: frontend `http://localhost:8080`, backend
`http://localhost:8000`, GenAI `http://localhost:8001`. O banco operacional
local é `data/rocketlab.db`; o volume Docker legado é lido somente durante uma
migração inicial, se esse arquivo ainda não existir.

## Gold, consultas e segurança

- O objeto Gold é `data/cinerocket.db`, controlado por Git LFS e montado como
  somente leitura no backend e no GenAI. Não o copie para as imagens Docker.
- O manifesto `data/cinerocket.db.sha256` contém SHA-256 e tamanho. Atualize-o
  junto com qualquer versão intencionalmente nova do Gold.
- O executor GenAI permite uma instrução `SELECT`, aplica allowlist de tabelas,
  valida com parser e executa em SQLite `mode=ro`; também limita linhas e tempo.
- As agregações e respostas seguem `genai/metric-rules.md`, o esquema em
  `genai/gold-schema.md` e as consultas de referência em
  `genai/reference-queries.sql`.
- O endpoint de perguntas é `POST http://localhost:8001/api/v1/questions`.
  O backend CineData não mantém mais a rota Gemini legada.
- Nunca adicione `.env`, segredos ou `data/rocketlab.db` ao Git. `.env.example`
  contém somente nomes/valores vazios ou padrões não secretos.

## Testes e limites do provedor

Os testes locais não precisam de chave e não chamam o Gemini:

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

Execute cada sequência a partir da raiz do repositório (em terminais separados)
ou retorne à raiz antes de iniciar a próxima. Para uma validação real, faça uma
pergunta manual, sem retries automáticos. Tool calling pode usar mais de uma
requisição por pergunta; planeje considerando o limite diário configurado no
provedor e evite avaliações em lote com chamadas reais.

## Convenções de mudança

- Para o próximo bloco de orientação da plataforma, conferir funcionalidades
  no frontend e nas rotas do backend. Manter esse conteúdo versionado e
  separado das métricas Gold; perguntas sobre uso do site não devem virar
  consultas SQL. O botão Ajuda deve sugerir apenas perguntas suportadas.
- Faça mudanças coesas e checkpoints revisáveis; não crie commits ou publique
  alterações sem pedido explícito.
- Mantenha agente e acesso ao Gold dentro de `genai/`; não acople o GenAI aos
  modelos ou à sessão de banco do backend existente.
- Preserve o layout do CineData, mantendo no frontend somente apresentação,
  envio de pergunta e renderização dos metadados/resultados.
- Atualize README/TODO quando execução, contratos ou decisões arquiteturais
  mudarem; não marque critérios como concluídos sem verificação correspondente.
