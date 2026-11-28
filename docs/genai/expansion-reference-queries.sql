-- Q15: Documentários por nota IMDb.
SELECT m.titulo, m.ano_lancamento, f.nota_imdb, f.qtd_imdb
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE g.nome_genero = 'Documentary' AND m.ano_lancamento BETWEEN 2016 AND 2024
  AND f.qtd_imdb >= 1000 AND f.nota_imdb BETWEEN 0 AND 10
ORDER BY f.nota_imdb DESC, f.qtd_imdb DESC, m.titulo, m.sk_movie_id LIMIT 10;

-- Q16: Anos com mais terror que comédia.
WITH counts AS (
    SELECT m.ano_lancamento, SUM(g.nome_genero = 'Horror') AS terror,
           SUM(g.nome_genero = 'Comedy') AS comedia
    FROM dim_movies m JOIN bridge_movie_genre b USING (sk_movie_id)
    JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento BETWEEN 2016 AND 2024 AND g.nome_genero IN ('Horror', 'Comedy')
    GROUP BY m.ano_lancamento
)
SELECT *, terror - comedia AS diferenca FROM counts WHERE terror > comedia ORDER BY ano_lancamento;

-- Q17: Lucro com orçamento limitado.
SELECT m.titulo, f.orcamento_brl, f.receita_brl, f.receita_brl - f.orcamento_brl AS lucro_brl
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
WHERE f.orcamento_brl BETWEEN 0 AND 10000000 AND f.receita_brl IS NOT NULL
ORDER BY lucro_brl DESC, m.titulo, m.sk_movie_id LIMIT 5;

-- Q18: Ranking IMDb com diferença para TMDB.
SELECT m.titulo, f.nota_imdb, f.nota_tmdb, f.qtd_imdb,
       f.nota_imdb - f.nota_tmdb AS diferenca
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
WHERE f.qtd_imdb >= 5000 AND f.qtd_tmdb > 0
  AND f.nota_imdb BETWEEN 0 AND 10 AND f.nota_tmdb BETWEEN 0 AND 10
  AND f.nota_imdb - f.nota_tmdb >= 1
ORDER BY f.nota_imdb DESC, f.qtd_imdb DESC, m.titulo, m.sk_movie_id LIMIT 5;

-- Q19: Ano de maior média IMDb em animação.
SELECT m.ano_lancamento, AVG(f.nota_imdb) AS nota_media_imdb, COUNT(*) AS filmes_avaliados
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE g.nome_genero = 'Animation' AND m.ano_lancamento BETWEEN 2016 AND 2024
  AND f.qtd_imdb > 0 AND f.nota_imdb BETWEEN 0 AND 10
GROUP BY m.ano_lancamento HAVING COUNT(*) >= 10
ORDER BY nota_media_imdb DESC, m.ano_lancamento LIMIT 1;

-- Q20: Diretores de Leonardo DiCaprio.
WITH filmes AS (
    SELECT DISTINCT b.sk_movie_id
    FROM bridge_movie_person b JOIN dim_people p USING (sk_person_id)
    WHERE p.tipo_pessoa = 'Ator' AND p.nome_pessoa = 'Leonardo DiCaprio' COLLATE NOCASE
), creditos AS (
    SELECT p.sk_person_id, p.nome_pessoa, b.sk_movie_id,
           CASE WHEN f.qtd_imdb > 0 AND f.nota_imdb BETWEEN 0 AND 10 THEN f.nota_imdb END AS nota
    FROM filmes JOIN bridge_movie_person b USING (sk_movie_id)
    JOIN dim_people p USING (sk_person_id)
    LEFT JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE p.tipo_pessoa = 'Diretor'
)
SELECT nome_pessoa AS diretor, COUNT(*) AS filmes_em_comum,
       COUNT(nota) AS filmes_avaliados, AVG(nota) AS nota_media_imdb
FROM creditos GROUP BY sk_person_id, nome_pessoa HAVING COUNT(*) >= 2
ORDER BY nota_media_imdb DESC, filmes_em_comum DESC, diretor, sk_person_id;

-- Q21: Gêneros por lucro médio e proporção lucrativa.
SELECT g.nome_genero, AVG(f.receita_brl - f.orcamento_brl) AS lucro_medio_brl,
       COUNT(*) AS filmes_elegiveis, 100.0 * AVG(f.receita_brl > f.orcamento_brl) AS percentual_lucrativo
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.ano_lancamento BETWEEN 2016 AND 2024
  AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
GROUP BY g.sk_genre_id, g.nome_genero ORDER BY lucro_medio_brl DESC, g.nome_genero LIMIT 3;

-- Q22: Proporção lucrativa em ficção científica.
SELECT COUNT(*) AS filmes_elegiveis, COUNT(CASE WHEN f.receita_brl > f.orcamento_brl THEN 1 END) AS filmes_lucrativos,
       100.0 * AVG(f.receita_brl > f.orcamento_brl) AS percentual_lucrativo
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.ano_lancamento BETWEEN 2016 AND 2024 AND g.nome_genero = 'Science Fiction'
  AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL;

-- Q23: Produtoras por proporção lucrativa, incluindo mediana.
WITH ranked AS (
    SELECT b.sk_company_id, f.receita_brl - f.orcamento_brl AS lucro,
           ROW_NUMBER() OVER (PARTITION BY b.sk_company_id ORDER BY f.receita_brl - f.orcamento_brl, b.sk_movie_id) AS pos,
           COUNT(*) OVER (PARTITION BY b.sk_company_id) AS total
    FROM bridge_movie_company b JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
)
SELECT c.nome_produtora, COUNT(*) AS filmes_elegiveis, SUM(r.lucro > 0) AS filmes_lucrativos,
       100.0 * AVG(r.lucro > 0) AS percentual_lucrativo,
       AVG(CASE WHEN r.pos IN ((r.total + 1) / 2, (r.total + 2) / 2) THEN r.lucro END) AS lucro_mediano_brl
FROM ranked r JOIN dim_companies c USING (sk_company_id)
GROUP BY r.sk_company_id, c.nome_produtora HAVING COUNT(*) >= 10
ORDER BY percentual_lucrativo DESC, filmes_elegiveis DESC, c.nome_produtora, r.sk_company_id LIMIT 5;

-- Q24: Lucro entre filmes de nota alta e receita superior ao dobro do orçamento.
SELECT m.titulo, m.ano_lancamento, f.nota_imdb, f.qtd_imdb,
       f.receita_brl - f.orcamento_brl AS lucro_brl
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
WHERE m.data_lancamento BETWEEN '2016-01-01' AND DATE('now')
  AND f.nota_imdb BETWEEN 8 AND 10 AND f.qtd_imdb >= 10000
  AND f.orcamento_brl > 0 AND f.receita_brl > 2 * f.orcamento_brl
ORDER BY lucro_brl DESC, m.titulo, m.sk_movie_id LIMIT 10;
