-- Consultas de referência para validar as definições em metric-rules.md.
-- Executar somente contra data/cinerocket.db em modo somente leitura.

-- Q01: Top 10 de receita BRL; o orçamento não participa da população.
SELECT m.sk_movie_id, m.titulo, f.receita_brl
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE f.receita_brl IS NOT NULL
ORDER BY f.receita_brl DESC, m.titulo COLLATE NOCASE, m.sk_movie_id
LIMIT 10;

-- Q02: lucro médio em BRL por gênero; associação declarada por filme/gênero.
WITH film_profit AS (
    SELECT sk_movie_id, receita_brl - orcamento_brl AS lucro_brl
    FROM fact_movies_performance
    WHERE receita_brl IS NOT NULL AND orcamento_brl IS NOT NULL
),
film_genre AS (
    SELECT DISTINCT sk_movie_id, sk_genre_id FROM bridge_movie_genre
)
SELECT g.nome_genero, COUNT(*) AS filmes_elegiveis,
       AVG(p.lucro_brl) AS lucro_medio_brl
FROM film_profit AS p
JOIN film_genre AS bg USING (sk_movie_id)
JOIN dim_genres AS g USING (sk_genre_id)
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY lucro_medio_brl DESC, g.nome_genero COLLATE NOCASE, g.sk_genre_id;

-- Q03: maiores margens de filmes com receita > 0 e orçamento conhecido.
SELECT m.sk_movie_id, m.titulo,
       1.0 * (f.receita_brl - f.orcamento_brl) / f.receita_brl AS margem
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE f.receita_brl > 0 AND f.orcamento_brl IS NOT NULL
ORDER BY margem DESC, m.titulo COLLATE NOCASE, m.sk_movie_id
LIMIT 10;

-- Q04: top 5 por popularidade; zero permanece como valor observado.
WITH limite AS (
    SELECT popularidade
    FROM fact_movies_performance
    WHERE popularidade IS NOT NULL
    ORDER BY popularidade DESC
    LIMIT 1 OFFSET 4
), candidatos AS MATERIALIZED (
    SELECT f.sk_movie_id, f.popularidade
    FROM fact_movies_performance AS f
    WHERE f.popularidade IS NOT NULL
      AND f.popularidade >= (SELECT popularidade FROM limite)
)
SELECT m.sk_movie_id, m.titulo, c.popularidade
FROM candidatos AS c
JOIN dim_movies AS m ON m.sk_movie_id = c.sk_movie_id
ORDER BY c.popularidade DESC, m.titulo COLLATE NOCASE, m.sk_movie_id
LIMIT 5;

-- Q05: divergência absoluta TMDB/IMDb; requer votos positivos nas duas fontes.
SELECT m.sk_movie_id, m.titulo,
       ABS(f.nota_tmdb - f.nota_imdb) AS divergencia,
       f.nota_tmdb, f.qtd_tmdb, f.nota_imdb, f.qtd_imdb
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE f.nota_tmdb IS NOT NULL AND f.qtd_tmdb > 0
  AND f.nota_imdb IS NOT NULL AND f.qtd_imdb > 0
ORDER BY divergencia DESC, m.titulo COLLATE NOCASE, m.sk_movie_id
LIMIT 10;

-- Q06: média IMDb por ano até a data atual; observação válida exige ao menos um voto.
SELECT m.ano_lancamento, COUNT(*) AS filmes_validos,
       AVG(f.nota_imdb) AS nota_imdb_media
FROM dim_movies AS m
JOIN fact_movies_performance AS f USING (sk_movie_id)
WHERE m.ano_lancamento IS NOT NULL
  AND m.data_lancamento <= date('now')
  AND f.nota_imdb IS NOT NULL AND f.qtd_imdb > 0
GROUP BY m.ano_lancamento
ORDER BY m.ano_lancamento ASC;

-- Q07: ator(es) com mais filmes na janela móvel; retorna todos os empatados.
WITH recent_movies AS MATERIALIZED (
    SELECT sk_movie_id
    FROM dim_movies
    WHERE data_lancamento >= date('now', '-5 years')
      AND data_lancamento <= date('now')
), actor_films AS (
    SELECT p.sk_person_id, p.nome_pessoa,
           COUNT(*) AS total_filmes
    FROM recent_movies AS rm
    JOIN bridge_movie_person AS bp USING (sk_movie_id)
    JOIN dim_people AS p USING (sk_person_id)
    WHERE p.tipo_pessoa = 'Ator'
    GROUP BY p.sk_person_id, p.nome_pessoa
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY total_filmes DESC) AS posicao
    FROM actor_films
)
SELECT sk_person_id, nome_pessoa, total_filmes
FROM ranked WHERE posicao = 1
ORDER BY nome_pessoa COLLATE NOCASE, sk_person_id;

-- Q08: diretores com maior média IMDb; mínimo de cinco filmes com nota válida.
WITH director_movies AS (
    SELECT p.sk_person_id, p.nome_pessoa, bp.sk_movie_id, f.nota_imdb
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp USING (sk_person_id)
    JOIN fact_movies_performance AS f USING (sk_movie_id)
    WHERE p.tipo_pessoa = 'Diretor'
      AND f.nota_imdb IS NOT NULL AND f.qtd_imdb > 0
), director_avgs AS (
    SELECT sk_person_id, nome_pessoa, COUNT(*) AS filmes_validos,
           AVG(nota_imdb) AS nota_media
    FROM director_movies
    GROUP BY sk_person_id, nome_pessoa
    HAVING COUNT(*) >= 5
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY nota_media DESC) AS posicao
    FROM director_avgs
)
SELECT sk_person_id, nome_pessoa, filmes_validos, nota_media
FROM ranked WHERE posicao = 1
ORDER BY nome_pessoa COLLATE NOCASE, sk_person_id;

-- Q09: dupla ator-diretor mais frequente por filmes distintos em comum.
WITH actor_links AS MATERIALIZED (
    SELECT bp.sk_movie_id, p.sk_person_id
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp ON bp.sk_person_id = p.sk_person_id
    WHERE p.tipo_pessoa = 'Ator'
), director_links AS MATERIALIZED (
    SELECT bp.sk_movie_id, p.sk_person_id
    FROM dim_people AS p
    JOIN bridge_movie_person AS bp ON bp.sk_person_id = p.sk_person_id
    WHERE p.tipo_pessoa = 'Diretor'
), pair_counts AS MATERIALIZED (
    SELECT a.sk_person_id AS actor_id, d.sk_person_id AS director_id,
           COUNT(*) AS filmes_em_comum
    FROM actor_links AS a
    JOIN director_links AS d ON d.sk_movie_id = a.sk_movie_id
    WHERE a.sk_person_id <> d.sk_person_id
    GROUP BY a.sk_person_id, d.sk_person_id
), max_count AS (
    SELECT MAX(filmes_em_comum) AS filmes_em_comum
    FROM pair_counts
)
SELECT ap.nome_pessoa AS ator, dp.nome_pessoa AS diretor, pc.filmes_em_comum
FROM pair_counts AS pc
JOIN max_count AS mc USING (filmes_em_comum)
JOIN dim_people AS ap ON ap.sk_person_id = pc.actor_id
JOIN dim_people AS dp ON dp.sk_person_id = pc.director_id
ORDER BY ator COLLATE NOCASE, diretor COLLATE NOCASE, pc.actor_id, pc.director_id;

-- Q10: filmes distintos associados a cada gênero.
SELECT g.nome_genero, COUNT(DISTINCT bg.sk_movie_id) AS total_filmes
FROM dim_genres AS g
JOIN bridge_movie_genre AS bg USING (sk_genre_id)
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY total_filmes DESC, g.nome_genero COLLATE NOCASE, g.sk_genre_id;

-- Q11: lucro total por produtora; lucro do filme inteiro é atribuído a cada
-- produtora associada, portanto totais entre produtoras não são aditivos.
WITH film_profit AS (
    SELECT sk_movie_id, receita_brl - orcamento_brl AS lucro_brl
    FROM fact_movies_performance
    WHERE receita_brl IS NOT NULL AND orcamento_brl IS NOT NULL
), company_totals AS (
    SELECT c.sk_company_id, c.nome_produtora, COUNT(*) AS filmes_elegiveis,
           SUM(p.lucro_brl) AS lucro_total_brl
    FROM film_profit AS p
    JOIN bridge_movie_company AS bc USING (sk_movie_id)
    JOIN dim_companies AS c USING (sk_company_id)
    GROUP BY c.sk_company_id, c.nome_produtora
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY lucro_total_brl DESC) AS posicao
    FROM company_totals
)
SELECT sk_company_id, nome_produtora, filmes_elegiveis, lucro_total_brl
FROM ranked WHERE posicao = 1
ORDER BY nome_produtora COLLATE NOCASE, sk_company_id;

-- Q12: maior margem média por gênero; margem primeiro calculada por filme.
WITH film_margin AS (
    SELECT sk_movie_id,
           1.0 * (receita_brl - orcamento_brl) / receita_brl AS margem
    FROM fact_movies_performance
    WHERE receita_brl > 0 AND orcamento_brl IS NOT NULL
), film_genre AS (
    SELECT DISTINCT sk_movie_id, sk_genre_id FROM bridge_movie_genre
), genre_avgs AS (
    SELECT g.sk_genre_id, g.nome_genero, COUNT(*) AS filmes_validos,
           AVG(fm.margem) AS margem_media
    FROM film_margin AS fm
    JOIN film_genre AS bg USING (sk_movie_id)
    JOIN dim_genres AS g USING (sk_genre_id)
    GROUP BY g.sk_genre_id, g.nome_genero
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY margem_media DESC) AS posicao
    FROM genre_avgs
)
SELECT sk_genre_id, nome_genero, filmes_validos, margem_media
FROM ranked WHERE posicao = 1
ORDER BY nome_genero COLLATE NOCASE, sk_genre_id;

-- Q13: filmes com maior quantidade de avaliações de usuários (resumo por filme).
WITH ranked AS (
    SELECT r.sk_movie_id, r.qtd_avaliacoes_usuarios,
           DENSE_RANK() OVER (ORDER BY r.qtd_avaliacoes_usuarios DESC) AS posicao
    FROM dim_reviews AS r
)
SELECT m.sk_movie_id, m.titulo, r.qtd_avaliacoes_usuarios
FROM ranked AS r
JOIN dim_movies AS m USING (sk_movie_id)
WHERE r.posicao = 1
ORDER BY m.titulo COLLATE NOCASE, m.sk_movie_id;

-- Q14: maior divergência entre resumo de nota dos usuários e nota IMDb.
WITH differences AS (
    SELECT m.sk_movie_id, m.titulo, r.nota_media_usuarios,
           f.nota_imdb, r.qtd_avaliacoes_usuarios, f.qtd_imdb,
           ABS(r.nota_media_usuarios - f.nota_imdb) AS divergencia
    FROM dim_reviews AS r
    JOIN dim_movies AS m USING (sk_movie_id)
    JOIN fact_movies_performance AS f USING (sk_movie_id)
    WHERE r.qtd_avaliacoes_usuarios > 0
      AND r.nota_media_usuarios IS NOT NULL
      AND f.nota_imdb IS NOT NULL AND f.qtd_imdb > 0
), ranked AS (
    SELECT *, DENSE_RANK() OVER (ORDER BY divergencia DESC) AS posicao
    FROM differences
)
SELECT sk_movie_id, titulo, nota_media_usuarios, nota_imdb,
       qtd_avaliacoes_usuarios, qtd_imdb, divergencia
FROM ranked WHERE posicao = 1
ORDER BY titulo COLLATE NOCASE, sk_movie_id;
