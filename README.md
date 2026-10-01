# CineData GenAI

Projeto da atividade **GenAI - CineData Analytics**, do Visagio Rocket Lab
2026.2. O objetivo é criar um agente em Python que responda perguntas de negócio
em linguagem natural consultando, em tempo real e somente para leitura, a camada
Gold do catálogo de filmes por meio de Text-to-SQL.

O escopo da atividade GenAI ainda está em planejamento. O módulo, o serviço e a
integração com a interface não foram implementados. A aplicação CineData
existente e sua interface permanecem o foco desta etapa.

![Página inicial do CineData com destaque para Spider-Man: Across the Spider-Verse](docs/images/home.png)

## Aplicação

A aplicação existente reúne frontend React e backend FastAPI. O banco Gold é
montado somente para leitura e o banco operacional fica persistido no diretório
do projeto. Acompanhe o
[plano da atividade](docs/.ruler/TODO.md).

O Gold `data/cinerocket.db` fica junto dos dados do projeto e está configurado
para distribuição pelo Git LFS. Instale o Git LFS antes de clonar; para um clone
já feito, rode `git lfs install` e `git lfs pull`. O Compose valida o arquivo antes
de iniciar; um pointer LFS sem o objeto real resulta em erro explicativo. O
manifesto `data/cinerocket.db.sha256` acompanha o Gold para evitar reler o banco
inteiro em cada inicialização. Se o dataset mudar, atualize hash e tamanho no
manifesto junto com o objeto LFS. O
sincronizador também aceita `GOLD_DATABASE_PATH` ou `--gold-database`. O esquema
e suas limitações estão no guia de
[banco de dados](docs/database.md). O backend importa as tabelas para o SQLite
operacional sem sobrescrever contas, listas, avaliações ou comunidades. O Gold
é montado somente para leitura. Ele contém `dim_movies`,
`fact_movies_performance`, `dim_genres`, `dim_people`, `dim_companies`,
`dim_reviews`, `movie_reviews`, `bridge_movie_genre`, `bridge_movie_person` e
`bridge_movie_company`.

## Perguntas que o agente deve cobrir

- **Bilheteria e finanças:** maiores receitas, lucro médio por gênero e maiores
  margens entre filmes com orçamento e receita informados.
- **Popularidade e engajamento:** filmes mais populares, divergência entre
  notas TMDB e IMDb, e nota IMDb média por ano.
- **Elenco e equipe:** atores mais ativos nos últimos cinco anos, diretores com
  maior média (mínimo de cinco filmes) e duplas ator-diretor mais frequentes.
- **Gêneros e produtoras:** contagem por gênero, maior lucro total por produtora
  e maior margem média por gênero.
- **Avaliações de usuários:** filmes mais avaliados e maior diferença entre a
  nota média de usuários e a nota IMDb.

Receita, faturamento e bilheteria são termos equivalentes na atividade. Os
exemplos são um ponto de partida; outras análises também são bem-vindas.

## Aplicação existente e banco Gold

O `docker-compose.yml` inicia a aplicação CineData existente. O backend
sincroniza o catálogo Gold de forma transacional e preserva os registros de uso.
O SQLite operacional fica em `./data/rocketlab.db`,
dentro do projeto e fora do Git. Na primeira inicialização, um preparador copia
o banco do volume Docker legado se ainda não houver cópia local; o volume
original permanece intacto. O Gold usa Git LFS; não adicione ZIPs,
segredos ou bancos operacionais ao Git.

Com Docker Desktop instalado, execute na raiz:

```powershell
docker compose up --build
```

Na inicialização, o preparador valida o Gold e preserva/migra o banco operacional
para `./data`; depois o backend aplica migrações e importa o Gold montado em
leitura. Em uma atualização futura, o fingerprint sincroniza o catálogo sem
apagar contas, listas, comunidades ou avaliações de usuários. Uma migração de
banco operacional já usado cria backup com sufixo `.pre-gold-<data>.db`. A
primeira sincronização pode levar vários minutos.

O frontend fica em `http://localhost:8080` e a API em
`http://localhost:8000`.

Para executar a migração Gold localmente sem Docker, após aplicar as migrações
do backend, rode em `backend/`:

```powershell
python -m app.db.gold_seed --database-url "sqlite+aiosqlite:///./rocketlab.db"
```

Sem `--gold-database`, o comando procura `data/cinerocket.db`.
Use `--gold-database <caminho>` ou configure `GOLD_DATABASE_PATH` para outro
local. O comando valida as tabelas esperadas, sincroniza em lotes e não altera
o arquivo Gold original. Se o arquivo não for encontrado, exibe como obtê-lo e
como configurar o caminho.

## Segurança e limites

Quando o módulo GenAI for planejado e autorizado, as regras de leitura do Gold,
credenciais e limites de chamadas deverão ser definidos antes de implementar
consultas a modelos externos.

## Prazo da atividade

Entrega até **segunda-feira, 5 de outubro de 2026, às 18:00**. O projeto e o
README devem estar versionados no GitHub e incluir instruções para executar a
aplicação.
