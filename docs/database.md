# Backend: dados Gold e persistência

Este documento descreve a camada Gold usada pelo catálogo, o banco operacional
da aplicação, as relações entre ambos e o ciclo de sincronização. Para iniciar
os serviços, consulte o [README principal](../README.md); as rotas estão em
[backend e API v1](backend.md).

## Fonte do catálogo

`cinerocket.db` é a fonte canônica dos dados analíticos e de catálogo. É um
arquivo SQLite distribuído via Git LFS e montado como somente leitura. O
Compose aplica as migrações no banco operacional e sincroniza a camada Gold
antes de iniciar a API. O catálogo ativo da aplicação contém os dados Gold e
essa é a única fonte usada para popular suas tabelas.

O arquivo recebido contém dez tabelas analíticas Gold e uma tabela auxiliar
`alembic_version` que não pertence ao domínio Gold. O importador lê apenas as
dez tabelas listadas abaixo. A tabela técnica auxiliar não é usada em consultas
analíticas.

## Dicionário da camada Gold

As contagens são a fotografia observada em 30/09/2026 e podem mudar quando a
fonte for atualizada. `sk_*` são chaves substitutas do dataset. Valores `_usd`
e `_brl` pertencem a moedas diferentes e não devem ser somados ou comparados sem
conversão explícita.

| Tabela | Grão, campos e semântica |
| --- | --- |
| `dim_movies` | 95.645 filmes. PK `sk_movie_id`; identificador de negócio `id_filme`; `titulo`, `data_lancamento`, `ano_lancamento`, `duracao_minutos`, `idioma_original`, `status_filme`, `sinopse`, `url_poster` e `url_backdrop`. Datas e duração podem ser nulas. `idioma_original` existe no esquema, mas estava nulo em todas as 95.645 linhas inspecionadas. |
| `fact_movies_performance` | Uma linha por filme (95.645), PK/FK `sk_movie_id`; `orcamento_usd`, `receita_usd`, `lucro_usd`, `orcamento_brl`, `receita_brl`, `lucro_brl`, `popularidade`, `nota_tmdb`, `qtd_tmdb`, `nota_imdb` e `qtd_imdb`. Valores financeiros podem ser desconhecidos; notas TMDB e IMDb são métricas distintas. |
| `dim_genres` | 19 gêneros. `sk_genre_id` PK e `nome_genero` único. Liga-se a filmes por `bridge_movie_genre`. |
| `dim_people` | 424.656 registros de pessoa/papel. `sk_person_id` PK; `nome_pessoa`, `tipo_pessoa`. Os papéis observados são `Ator`, `Diretor` e `Roteirista`; liga-se a filmes por `bridge_movie_person`. |
| `dim_companies` | 45.941 produtoras/estúdios. `sk_company_id` PK e `nome_produtora` único; liga-se a filmes por `bridge_movie_company`. |
| `dim_reviews` | 40.267 resumos, um por filme. `sk_review_id` PK; `sk_movie_id` único/FK; `qtd_avaliacoes_usuarios` e `nota_media_usuarios`. A média pode ser nula. |
| `movie_reviews` | 43.666 avaliações individuais. `id` PK; `sk_movie_review_id`, `sk_movie_id` FK, `name`, `rating`, `text` e `created_at`. O sincronizador mapeia os três campos textuais/de nota para `nome`, `nota` e `comentario` no schema da aplicação. |
| `bridge_movie_genre` | 121.521 pares filme/gênero. Chave primária composta pelos IDs do filme e gênero, ambos FKs. Relação N:N. |
| `bridge_movie_person` | 745.450 pares filme/pessoa. Chave primária composta pelos IDs do filme e pessoa, ambos FKs. Relação N:N; interpretar a pessoa segundo `tipo_pessoa`. |
| `bridge_movie_company` | 116.326 pares filme/produtora. Chave primária composta pelos IDs do filme e produtora, ambos FKs. Relação N:N. |

As bridges são multivaloradas. Juntá-las a fatos financeiros antes de agregar
pode multiplicar valores quando um filme possui vários gêneros, profissionais
ou produtoras. Agregue no grão do filme antes de expandir dimensões, ou explique
explicitamente a regra de atribuição. Para análises de margem, exigir receita e
orçamento informados, tratar receita zero e declarar a fórmula. Não misture
`dim_reviews` (resumo Gold) e `movie_reviews` (avaliações individuais) sem
definir a população desejada.

## Convenções analíticas para as perguntas da atividade

- Perguntas com valor em reais usam `receita_brl`, `orcamento_brl` e
  `lucro_brl`; valores `_usd` nunca são misturados com `_brl`. Lucro é
  `lucro_brl` (equivalente a receita menos orçamento) somente quando os dados
  necessários estão disponíveis. Margem é `lucro_brl / receita_brl` e exige
  receita maior que zero.
- Filmes com receita ausente ficam fora de rankings de receita. Lucro médio
  por gênero inclui apenas filmes com receita informada e lucro calculável;
  margem exige também orçamento e receita válidos. Totais por gênero/produtora
  são agregados por filme antes de expandir relações multivaloradas.
- “Últimos cinco anos” é uma janela móvel contada da data de execução até cinco
  anos antes, usando `data_lancamento`; contagens de atuação são de filmes
  distintos.
- O Gold observado registra TMDB, IMDb e média dos usuários entre 0 e 10;
  divergência usa diferença absoluta. “Nota média” de diretores usa `nota_imdb`,
  decisão uniforme para a pergunta sem fonte de nota explícita, com pelo menos
  cinco filmes distintos qualificados.
- Popularidade usa `popularidade`; a evolução anual usa `nota_imdb` e
  `ano_lancamento`. Perguntas sobre reviews de usuários usam
  `dim_reviews.qtd_avaliacoes_usuarios` e `dim_reviews.nota_media_usuarios`, que
  representam a população agregada disponibilizada no Gold. `movie_reviews` é
  população individual distinta e não substitui esse resumo automaticamente.
- Empates são ordenados por título ou nome em ordem alfabética para produzir
  resultados estáveis; a resposta pode explicitar que houve empate.

## Banco operacional da aplicação

O banco operacional `rocketlab.db` é a única base consultada pelo backend. Ele
contém as dimensões e fatos Gold sincronizados e também as tabelas próprias da
aplicação. A aplicação não mantém um catálogo inicial paralelo. O Gold original
permanece separado para ser fonte reproduzível e imutável; dados locais de
contas e atividade não são escritos nele.

| Grupo | Tabelas | Finalidade |
| --- | --- | --- |
| Catálogo Gold | `dim_movies`, `dim_genres`, `dim_people`, `dim_companies`, `fact_movies_performance`, `dim_reviews`, `movie_reviews` | Catálogo, métricas e avaliações importadas. Avaliações de usuários da aplicação ocupam `movie_reviews` com `user_id` preenchido; as importadas não têm conta local associada. |
| Relações do catálogo | `bridge_movie_genre`, `bridge_movie_person`, `bridge_movie_company` | Relacionamentos N:N com chaves compostas. |
| Contas e atividade | `users`, `user_lists`, `user_list_movies`, `watch_later_movies`, `friendship_requests`, `communities`, `community_memberships`, `community_posts`, `community_comments`, `community_reactions`, `chat_conversations`, `chat_messages` | Autenticação, listas, avaliações locais, amizades, conversas privadas e recursos sociais preservados na migração. |
| Controle | `alembic_version`, `gold_database_sync` | Revisão do schema operacional e fingerprint da fonte sincronizada. |

`users` guarda hashes de senha, nunca senhas em texto. Há no máximo uma
avaliação local por conta e filme, garantida por índice único parcial em
`(user_id, sk_movie_id)`. Uma avaliação removida de uma conta pode permanecer
sem vínculo para preservar o histórico. Chaves estrangeiras e políticas de
cascade/set-null mantêm as associações coerentes.

## Migrações e sincronização Gold

As migrações sequenciais ficam em
[`backend/migrations/versions/`](../backend/migrations/versions/); os modelos
ORM ficam em `backend/app/movies/models.py`, `backend/app/users/models.py` e
`backend/app/communities/models.py`. O Compose executa `alembic upgrade head` e
depois `python -m app.db.gold_seed` antes de iniciar a API.

O sincronizador lê o Gold com SQLite em modo somente leitura, valida as tabelas
e colunas esperadas e importa em lotes dentro de uma transação. Upserts usam as
chaves Gold; as relações usam chaves compostas. O fingerprint SHA-256 evita
reimportar a mesma fonte. Uma alteração do arquivo leva à sincronização seguinte
e cria backup preventivo do banco operacional se ele já contém dados. Avaliações
locais permanecem preservadas e o resumo de notas é recomposto considerando a
base Gold e essas avaliações.

Na primeira execução sem banco operacional ou volume legado, o snapshot Gold
conhecido é copiado diretamente para `rocketlab.db`. O preparador calcula o
SHA-256 durante a cópia, compara com o manifesto, converte `movie_reviews` para
o esquema da aplicação e verifica essa tabela. Depois, o Alembic aplica as
migrações; um marcador de uso único permite ao sincronizador registrar o
fingerprint sem repetir a importação linha a linha. O marcador é removido após
o registro. Se o snapshot Gold for diferente, o projeto usa a criação do banco
e a importação em lotes tradicionais. Um banco operacional existente nunca é
substituído pela cópia rápida.

O manifesto `data/cinerocket.db.sha256` guarda o SHA-256 e o tamanho do objeto
Gold distribuído via Git LFS. O Compose o monta somente para leitura junto ao
banco; assim, a API identifica a versão sem reler cerca de 722 MB a cada inicialização.
Ao atualizar o Gold, atualize também esse manifesto. Bases personalizadas sem
manifesto continuam usando hash integral.

A migração `0020_add_original_language` adiciona `idioma_original` ao modelo e
ao banco operacional, e o sincronizador importa a coluna. Migrações novas são
aplicadas no próximo início do serviço. O Gold `./data/cinerocket.db`
é montado em
`/workspace/cinerocket.db` somente para leitura; o banco operacional fica em
`/app/data/rocketlab.db`, mapeado para `./data/rocketlab.db` no host. Na primeira
subida, `project-data-init` copia o banco do volume legado somente quando o
arquivo local ainda não existe; mantém o volume de origem intacto. Sem banco
local ou legado, ele prepara a cópia rápida do Gold conhecido.

Para sincronização local, após obter o arquivo Gold e aplicar as migrações:

```powershell
python -m app.db.gold_seed --database-url "sqlite+aiosqlite:///./rocketlab.db"
```

O caminho padrão é `data/cinerocket.db`. Também é possível
usar `GOLD_DATABASE_PATH` ou `--gold-database <caminho>`. O Gold é versionado
via Git LFS; ZIPs e bancos operacionais permanecem fora do Git. O preparador
falha com instrução clara se o clone tiver apenas o pointer LFS ou se o Gold
não tiver o schema esperado.

### Desempenho local

O catálogo usa FTS5 com tokenizer trigram para pesquisar trechos de pelo menos
três caracteres em títulos, pessoas e produtoras. Buscas de um ou dois
caracteres preservam a semântica anterior com `LIKE`. Triggers mantêm os índices
sincronizados quando os dados do catálogo mudam. A contagem de resultados usa
`COUNT(*)` diretamente sobre as tabelas filtradas, sem materializar todas as
colunas dos filmes em uma subconsulta.

O SQLite operacional usa WAL, `synchronous=NORMAL`, cache de páginas de 64 MiB,
temporários em memória e timeout de lock de 5 segundos. WAL mantém leituras
disponíveis durante gravações; `NORMAL` melhora o desempenho, com a possibilidade
de perder a transação mais recente em uma falha abrupta de energia.

## Histórico de migrações

| Revisão | Alteração |
| --- | --- |
| `0001_initial_movie_schema` | Cria dimensões, fatos e relações do catálogo, métricas, resumos e avaliações individuais. |
| `0002_add_catalog_filter_index` | Índice para filtro por gênero. |
| `0003_add_local_users`–`0009_add_review_visibility` | Contas, avaliações locais, listas, trailers, avatares, amizades e visibilidade. |
| `0010_add_communities`–`0012_add_community_image` | Comunidades, participação, conversas, reações, visualizações e imagem. |
| `0013_unique_user_movie_review`–`0015_add_community_moderation` | Unicidade de avaliação local, índice FTS5 do mapa e moderação. |
| `0016_clean_movie_runtime`–`0018_add_dislike_reaction` | Higiene/validação de métricas e reação negativa. |
| `0019_track_gold_database_sync` | Fingerprint da fonte aplicada ao banco operacional. |
| `0020_add_original_language` | Importa o idioma original dos filmes para o schema operacional. |
| `0021_add_catalog_search_indexes` | FTS5 trigram para buscar trechos em títulos, pessoas e produtoras. |
| `0022_cache_gold_fingerprint` | Persiste checksum e tamanho do Gold para evitar hashing repetido. |
| `0024_add_chat_conversations` | Histórico privado do chatbot, mensagens e vínculo com a conta. |

O mapa de gostos usa o catálogo operacional e o índice SQLite FTS5 de sinopses.
Detalhes de rotas e limites estão em
[backend e API v1](backend.md).
