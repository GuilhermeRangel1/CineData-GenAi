# Inventário da camada Gold

Este documento registra o inventário físico do Gold usado pelo módulo GenAI.
É uma fotografia da base local inspecionada; as decisões de negócio aplicadas
na entrega estão em `metric-rules.md` e as consultas de referência em
`reference-queries.sql`. O serviço consulta o arquivo somente em modo leitura.

## Integridade e tabelas

- Arquivo: `data/cinerocket.db` (aproximadamente 689 MiB).
- `PRAGMA integrity_check`: `ok`.
- `PRAGMA foreign_key_check`: nenhuma violação encontrada.
- O esquema analítico contém dez tabelas Gold. `alembic_version` é metadado
  técnico de migração, não faz parte do conjunto analítico permitido.

| Tabela | Linhas | Chave / relação principal |
| --- | ---: | --- |
| `dim_movies` | 95.645 | `sk_movie_id` (PK); `id_filme` único |
| `fact_movies_performance` | 95.645 | `sk_movie_id` (PK e FK para filme) |
| `dim_genres` | 19 | `sk_genre_id` (PK); nome único |
| `dim_people` | 424.656 | `sk_person_id` (PK); nome + tipo únicos |
| `dim_companies` | 45.941 | `sk_company_id` (PK); nome único |
| `dim_reviews` | 40.267 | `sk_review_id` (PK); `sk_movie_id` único e FK |
| `movie_reviews` | 43.666 | `id` (PK); FK para filme; identificador textual único |
| `bridge_movie_genre` | 121.521 | PK composta filme + gênero; FKs para ambas dimensões |
| `bridge_movie_person` | 745.450 | PK composta filme + pessoa; FKs para ambas dimensões |
| `bridge_movie_company` | 116.326 | PK composta filme + produtora; FKs para ambas dimensões |

## Índices de consulta

A base inclui índices de apoio para rankings de pessoas: `dim_people(tipo_pessoa,
sk_person_id)` filtra atores e diretores; `bridge_movie_person(sk_person_id,
sk_movie_id)` atende às associações por pessoa sem buscar cada linha na tabela
principal. Eles aceleram a análise de créditos sem alterar as linhas Gold. O
serviço GenAI continua abrindo o arquivo em modo somente leitura.

## Colunas relevantes para as métricas

- `dim_movies`: `sk_movie_id`, `id_filme`, `titulo`, `data_lancamento`,
  `ano_lancamento`, `duracao_minutos`, `idioma_original`, `status_filme`,
  `sinopse`, `url_poster` e `url_backdrop`. A tabela Gold não possui
  `url_trailer`.
- `fact_movies_performance`: `orcamento_usd`, `receita_usd`, `lucro_usd`,
  `orcamento_brl`, `receita_brl`, `lucro_brl`, `popularidade`, `nota_tmdb`,
  `qtd_tmdb`, `nota_imdb` e `qtd_imdb`, vinculados ao filme por
  `sk_movie_id`.
- `dim_genres`: `sk_genre_id`, `nome_genero`.
- `dim_people`: `sk_person_id`, `nome_pessoa`, `tipo_pessoa`. Os tipos observados
  incluem `Ator`, `Diretor` e `Roteirista`.
- `dim_companies`: `sk_company_id`, `nome_produtora`.
- `dim_reviews`: `sk_review_id`, `sk_movie_id`, `qtd_avaliacoes_usuarios` e
  `nota_media_usuarios`.
- `movie_reviews`: `id`, `sk_movie_review_id`, `sk_movie_id`, `name`, `rating`,
  `text` e `created_at`. Não há `user_id`.
- As bridges associam filmes a gêneros, pessoas e produtoras. Cada relação é
  única pelo par de chaves e aponta para as dimensões correspondentes.

## Observações de qualidade consideradas nas métricas

- `orcamento_usd` está ausente em 87.719 linhas e `receita_usd` em 92.272;
  por isso, análises de lucro e margem usam somente filmes com os dois
  componentes disponíveis.
- `popularidade` está ausente em 3.615 linhas; `qtd_tmdb`, em 7.567;
  `nota_imdb`, em 12.674; `qtd_imdb`, em 10.866. As regras de validade ficam
  explícitas em cada métrica.
- Existem notas TMDB iguais a zero com diferentes quantidades de votos, então
  zero não deve ser convertido genericamente em ausente. As consultas de
  referência preservam esse tratamento.
- Datas de lançamento vão de 2016-01-01 a 2029-10-13; há três filmes com data
  posterior a 2026-10-01. A janela móvel de cinco anos exclui lançamentos
  futuros e usa limites explícitos.
- Há relações 1:N entre filme e gêneros, pessoas ou produtoras. Agregar fatos
  financeiros depois de expandir essas relações pode contar um filme várias
  vezes; as consultas usam a granularidade declarada em `metric-rules.md`.
- `dim_reviews` tem um resumo por filme e suas contagens correspondem às linhas
  agrupadas em `movie_reviews` nos dados inspecionados. A média do resumo tem
  arredondamento de até aproximadamente 0,005 em relação à média bruta.
- `movie_reviews` não identifica usuários por chave e todas as linhas têm o
  mesmo `created_at` (`2026-09-28 15:49:34`). Não interpretar `name` como
  identidade única de usuário nem essa coluna como série temporal sem evidência
  adicional.
- Os valores observados de `nota_tmdb` e `nota_imdb` estão em escala de 0 a 10;
  comparabilidade e tratamento de notas sem votos são definidos nas regras de
  divergência.

## Uso na entrega

As regras de população, nulos, escala, períodos e desempates já foram
formalizadas em `metric-rules.md`. As 14 consultas de referência e os cenários
de avaliação ficam em `reference-queries.sql` e `evaluation-cases.md`. Este
inventário continua útil para atualizar essas regras se uma nova versão do Gold
alterar o schema ou as contagens.
