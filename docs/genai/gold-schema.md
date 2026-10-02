# Inventário da camada Gold

Este documento registra o inventário físico inicial da base analítica usada
para planejar as métricas. É uma fotografia da base local inspecionada; não
substitui a validação das regras de negócio nem as consultas de referência, que
continuam pendentes na etapa 1. A base deve ser consultada em modo somente
leitura pelo futuro módulo analítico.

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

## Observações de qualidade a resolver na etapa 1

- `orcamento_usd` está ausente em 87.719 linhas e `receita_usd` em 92.272;
  portanto, valores de lucro armazenados não bastam para decidir quais filmes
  entram em análises que exigem os dois componentes.
- `popularidade` está ausente em 3.615 linhas; `qtd_tmdb`, em 7.567;
  `nota_imdb`, em 12.674; `qtd_imdb`, em 10.866. As notas e contagens precisam
  de políticas de validade explícitas em cada métrica.
- Existem notas TMDB iguais a zero com diferentes quantidades de votos, então
  zero não deve ser convertido genericamente em ausente. As distribuições e a
  população válida devem ser confirmadas com consultas de referência.
- Datas de lançamento vão de 2016-01-01 a 2029-10-13; há três filmes com data
  posterior a 2026-10-01. A janela de cinco anos precisa excluir lançamentos
  futuros e ser definida com limites explícitos.
- Há relações 1:N entre filme e gêneros, pessoas ou produtoras. Agregar fatos
  financeiros depois de expandir essas relações pode contar um filme várias
  vezes; primeiro é necessário definir a granularidade de filme e validar cada
  agregação.
- `dim_reviews` tem um resumo por filme e suas contagens correspondem às linhas
  agrupadas em `movie_reviews` nos dados inspecionados. A média do resumo tem
  arredondamento de até aproximadamente 0,005 em relação à média bruta.
- `movie_reviews` não identifica usuários por chave e todas as linhas têm o
  mesmo `created_at` (`2026-09-28 15:49:34`). Não interpretar `name` como
  identidade única de usuário nem essa coluna como série temporal sem evidência
  adicional.
- Os valores observados de `nota_tmdb` e `nota_imdb` estão em escala de 0 a 10;
  comparabilidade e tratamento de notas sem votos ainda precisam de decisão
  explícita antes da métrica de divergência.

## Próximo trabalho da etapa 1

Definir população, unidade de análise, colunas, nulos/zeros, filtros temporais,
unidade monetária e desempates para cada pergunta obrigatória; então escrever e
executar consultas SQL de referência com verificações de cardinalidade e
amostras. Este inventário, por si só, não certifica as métricas nem seus
resultados.
