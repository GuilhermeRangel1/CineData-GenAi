-- Q25: Participação dos dez maiores na bilheteria total de 2023.
WITH receitas AS (
    SELECT m.sk_movie_id, f.receita_brl
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.ano_lancamento = 2023 AND f.receita_brl IS NOT NULL
), top_dez AS (
    SELECT receita_brl FROM receitas ORDER BY receita_brl DESC, sk_movie_id LIMIT 10
)
SELECT 100.0 * (SELECT SUM(receita_brl) FROM top_dez)
       / NULLIF(SUM(receita_brl), 0) AS percentual_bilheteria
FROM receitas;

-- Q26: Cinco maiores prejuízos em 2023.
SELECT m.titulo, f.orcamento_brl - f.receita_brl AS prejuizo_brl
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
WHERE m.ano_lancamento = 2023 AND f.receita_brl < f.orcamento_brl
ORDER BY prejuizo_brl DESC, m.titulo, m.sk_movie_id LIMIT 5;

-- Q27: Animações lançadas no ano passado que atingiram o ponto de equilíbrio.
SELECT m.titulo
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.data_lancamento >= DATE('now', 'start of year', '-1 year')
  AND m.data_lancamento < DATE('now', 'start of year')
  AND g.nome_genero = 'Animation' AND f.receita_brl >= f.orcamento_brl
ORDER BY m.titulo, m.sk_movie_id;

-- Q28: Filmes de ação já lançados neste ano com os dois dados financeiros.
SELECT m.titulo, f.orcamento_brl, f.receita_brl
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.data_lancamento BETWEEN DATE('now', 'start of year') AND DATE('now')
  AND g.nome_genero = 'Action'
  AND f.orcamento_brl IS NOT NULL AND f.receita_brl IS NOT NULL
ORDER BY m.titulo, m.sk_movie_id;

-- Q29: Prejuízos entre os cinco filmes mais caros.
WITH caros AS (
    SELECT m.sk_movie_id, m.titulo, f.orcamento_brl, f.receita_brl
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.ano_lancamento = 2023 AND f.orcamento_brl IS NOT NULL
    ORDER BY f.orcamento_brl DESC, m.titulo, m.sk_movie_id LIMIT 5
)
SELECT titulo, orcamento_brl - receita_brl AS prejuizo_brl
FROM caros WHERE receita_brl < orcamento_brl
ORDER BY orcamento_brl DESC, titulo, sk_movie_id;

-- Q30: Orçamento mediano dos filmes de terror.
WITH ordenados AS (
    SELECT f.orcamento_brl,
           ROW_NUMBER() OVER (ORDER BY f.orcamento_brl, m.sk_movie_id) AS posicao,
           COUNT(*) OVER () AS total
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento = 2024 AND g.nome_genero = 'Horror'
      AND f.orcamento_brl IS NOT NULL
)
SELECT AVG(orcamento_brl) AS orcamento_mediano_brl
FROM ordenados WHERE posicao IN ((total + 1) / 2, (total + 2) / 2);

-- Q31: Mais estreias de comédia e maior lucro médio de terror no mesmo ano.
WITH anuais AS (
    SELECT m.ano_lancamento, g.nome_genero, COUNT(*) AS estreias,
           AVG(f.receita_brl - f.orcamento_brl) AS lucro_medio
    FROM dim_movies m JOIN bridge_movie_genre b USING (sk_movie_id)
    JOIN dim_genres g USING (sk_genre_id)
    LEFT JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.data_lancamento <= DATE('now') AND m.ano_lancamento IS NOT NULL
      AND g.nome_genero IN ('Comedy', 'Horror')
    GROUP BY m.ano_lancamento, g.nome_genero
)
SELECT c.ano_lancamento, c.estreias AS qtd_comedia, t.estreias AS qtd_terror,
       c.lucro_medio AS lucro_medio_comedia, t.lucro_medio AS lucro_medio_terror
FROM anuais c JOIN anuais t USING (ano_lancamento)
WHERE c.nome_genero = 'Comedy' AND t.nome_genero = 'Horror'
  AND c.estreias > t.estreias AND t.lucro_medio > c.lucro_medio
ORDER BY c.ano_lancamento;

-- Q32: Maior aumento absoluto de bilheteria total por gênero.
WITH totais AS (
    SELECT g.sk_genre_id, g.nome_genero,
           SUM(CASE WHEN m.ano_lancamento = 2023 THEN f.receita_brl END) AS receita_2023,
           SUM(CASE WHEN m.ano_lancamento = 2022 THEN f.receita_brl END) AS receita_2022
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento IN (2022, 2023)
    GROUP BY g.sk_genre_id, g.nome_genero
)
SELECT nome_genero, receita_2023 - receita_2022 AS aumento_brl
FROM totais WHERE receita_2023 > receita_2022
ORDER BY aumento_brl DESC, nome_genero, sk_genre_id LIMIT 1;

-- Q33: Filmes presentes nos dois top 10.
WITH filmes AS (
    SELECT m.sk_movie_id, m.titulo, f.receita_brl,
           f.receita_brl - f.orcamento_brl AS lucro_brl
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.ano_lancamento = 2023
), por_receita AS (
    SELECT * FROM filmes WHERE receita_brl IS NOT NULL
    ORDER BY receita_brl DESC, titulo, sk_movie_id LIMIT 10
), por_lucro AS (
    SELECT sk_movie_id FROM filmes WHERE lucro_brl IS NOT NULL
    ORDER BY lucro_brl DESC, titulo, sk_movie_id LIMIT 10
)
SELECT r.titulo FROM por_receita r JOIN por_lucro USING (sk_movie_id)
ORDER BY r.receita_brl DESC, r.titulo, r.sk_movie_id;

-- Q34: Gênero com maior cobertura de orçamento e bilheteria.
SELECT g.nome_genero,
       100.0 * AVG(f.orcamento_brl IS NOT NULL AND f.receita_brl IS NOT NULL) AS percentual_informado
FROM dim_movies m JOIN bridge_movie_genre b USING (sk_movie_id)
JOIN dim_genres g USING (sk_genre_id)
LEFT JOIN fact_movies_performance f USING (sk_movie_id)
WHERE m.ano_lancamento = 2024
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY percentual_informado DESC, g.nome_genero, g.sk_genre_id LIMIT 1;

-- Q35: Receita por real de orçamento para animações.
SELECT 1.0 * SUM(f.receita_brl) / NULLIF(SUM(f.orcamento_brl), 0) AS receita_por_real
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.ano_lancamento = 2023 AND g.nome_genero = 'Animation'
  AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL;

-- Q37: Estreias por gênero em uma janela móvel de cinco anos.
SELECT g.nome_genero, COUNT(DISTINCT m.sk_movie_id) AS total_filmes
FROM dim_movies m JOIN bridge_movie_genre b USING (sk_movie_id)
JOIN dim_genres g USING (sk_genre_id)
WHERE m.data_lancamento BETWEEN DATE('now', '-5 years') AND DATE('now')
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY total_filmes DESC, g.nome_genero, g.sk_genre_id;

-- Q38: Elenco de Barbie (2023).
SELECT DISTINCT p.nome_pessoa
FROM dim_movies m JOIN bridge_movie_person b USING (sk_movie_id)
JOIN dim_people p USING (sk_person_id)
WHERE m.titulo = 'Barbie' COLLATE NOCASE AND m.ano_lancamento = 2023
  AND p.tipo_pessoa = 'Ator'
ORDER BY p.nome_pessoa COLLATE NOCASE, p.nome_pessoa;

-- Q39: Filmes em que DiCaprio atuou sob direção de Scorsese.
SELECT m.titulo, m.ano_lancamento
FROM dim_movies m
WHERE EXISTS (
    SELECT 1 FROM bridge_movie_person b JOIN dim_people p USING (sk_person_id)
    WHERE b.sk_movie_id = m.sk_movie_id AND p.tipo_pessoa = 'Ator'
      AND p.nome_pessoa = 'Leonardo DiCaprio' COLLATE NOCASE
) AND EXISTS (
    SELECT 1 FROM bridge_movie_person b JOIN dim_people p USING (sk_person_id)
    WHERE b.sk_movie_id = m.sk_movie_id AND p.tipo_pessoa = 'Diretor'
      AND p.nome_pessoa = 'Martin Scorsese' COLLATE NOCASE
)
ORDER BY m.ano_lancamento, m.titulo, m.sk_movie_id;

-- Q40: As cinco duplas de atores com mais filmes de terror em comum em 2023.
WITH elenco AS MATERIALIZED (
    SELECT DISTINCT b.sk_movie_id, b.sk_person_id
    FROM bridge_movie_person b JOIN dim_movies m USING (sk_movie_id)
    JOIN dim_people p USING (sk_person_id)
    JOIN bridge_movie_genre bg USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento = 2023 AND p.tipo_pessoa = 'Ator' AND g.nome_genero = 'Horror'
), duplas AS (
    SELECT a.sk_person_id AS primeiro, b.sk_person_id AS segundo, COUNT(*) AS total_filmes
    FROM elenco a JOIN elenco b
      ON a.sk_movie_id = b.sk_movie_id AND a.sk_person_id < b.sk_person_id
    GROUP BY a.sk_person_id, b.sk_person_id
), nomes AS (
    SELECT MIN(a.nome_pessoa, b.nome_pessoa) AS ator_1,
           MAX(a.nome_pessoa, b.nome_pessoa) AS ator_2, d.total_filmes, d.primeiro, d.segundo
    FROM duplas d JOIN dim_people a ON a.sk_person_id = d.primeiro
    JOIN dim_people b ON b.sk_person_id = d.segundo
)
SELECT ator_1, ator_2, total_filmes FROM nomes
ORDER BY total_filmes DESC, ator_1, ator_2, primeiro, segundo LIMIT 5;

-- Q41: Diretores com terror e comédia na filmografia.
SELECT p.nome_pessoa AS diretor
FROM dim_people p JOIN bridge_movie_person b USING (sk_person_id)
JOIN dim_movies m USING (sk_movie_id) JOIN bridge_movie_genre bg USING (sk_movie_id)
JOIN dim_genres g USING (sk_genre_id)
WHERE p.tipo_pessoa = 'Diretor' AND m.data_lancamento BETWEEN '2016-01-01' AND DATE('now')
  AND g.nome_genero IN ('Horror', 'Comedy')
GROUP BY p.sk_person_id, p.nome_pessoa HAVING COUNT(DISTINCT g.nome_genero) = 2
ORDER BY p.nome_pessoa COLLATE NOCASE, p.sk_person_id LIMIT 10;

-- Q42: Produtoras por coproduções em 2024.
WITH coproducoes AS (
    SELECT b.sk_movie_id
    FROM bridge_movie_company b JOIN dim_movies m USING (sk_movie_id)
    WHERE m.ano_lancamento = 2024
    GROUP BY b.sk_movie_id HAVING COUNT(DISTINCT b.sk_company_id) >= 2
)
SELECT c.nome_produtora, COUNT(DISTINCT b.sk_movie_id) AS total_coproducoes
FROM coproducoes JOIN bridge_movie_company b USING (sk_movie_id)
JOIN dim_companies c USING (sk_company_id)
GROUP BY c.sk_company_id, c.nome_produtora
ORDER BY total_coproducoes DESC, c.nome_produtora COLLATE NOCASE, c.sk_company_id LIMIT 5;

-- Q43: Maior bilheteria de cada produtora líder em quantidade em 2023.
WITH creditos_ano AS MATERIALIZED (
    SELECT sk_company_id, sk_movie_id
    FROM dim_movies JOIN bridge_movie_company USING (sk_movie_id)
    WHERE ano_lancamento = 2023
), contagem AS MATERIALIZED (
    SELECT sk_company_id, COUNT(DISTINCT sk_movie_id) AS total
    FROM creditos_ano GROUP BY sk_company_id
), maiores AS MATERIALIZED (
    SELECT c.sk_company_id, c.nome_produtora, contagem.total
    FROM contagem JOIN dim_companies c USING (sk_company_id)
    ORDER BY total DESC, c.nome_produtora COLLATE NOCASE, c.sk_company_id LIMIT 5
), creditos AS MATERIALIZED (
    SELECT sk_company_id, sk_movie_id FROM creditos_ano
    WHERE sk_company_id IN (SELECT sk_company_id FROM maiores)
), filmes AS (
    SELECT p.*, m.titulo, f.receita_brl,
           ROW_NUMBER() OVER (
               PARTITION BY p.sk_company_id ORDER BY f.receita_brl DESC, m.titulo, m.sk_movie_id
           ) AS posicao
    FROM creditos JOIN maiores p USING (sk_company_id)
    JOIN dim_movies m USING (sk_movie_id) JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE f.receita_brl IS NOT NULL
)
SELECT nome_produtora, titulo, receita_brl FROM filmes WHERE posicao = 1
ORDER BY total DESC, nome_produtora COLLATE NOCASE, sk_company_id;

-- Q44: Produtora com mais diretores distintos em 2024.
SELECT c.nome_produtora, COUNT(DISTINCT p.sk_person_id) AS total_diretores
FROM dim_companies c JOIN bridge_movie_company bc USING (sk_company_id)
JOIN dim_movies m USING (sk_movie_id) JOIN bridge_movie_person bp USING (sk_movie_id)
JOIN dim_people p USING (sk_person_id)
WHERE m.ano_lancamento = 2024 AND p.tipo_pessoa = 'Diretor'
GROUP BY c.sk_company_id, c.nome_produtora
ORDER BY total_diretores DESC, c.nome_produtora COLLATE NOCASE, c.sk_company_id LIMIT 1;

-- Q45: Notas e votos mínimos em ambas as fontes em 2019.
SELECT m.titulo, f.nota_imdb, f.qtd_imdb, f.nota_tmdb, f.qtd_tmdb
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
WHERE m.ano_lancamento = 2019 AND f.nota_imdb BETWEEN 8 AND 10 AND f.nota_tmdb BETWEEN 8 AND 10
  AND f.qtd_imdb >= 10000 AND f.qtd_tmdb >= 10000
ORDER BY f.nota_imdb DESC, f.qtd_imdb DESC, m.titulo, m.sk_movie_id;

-- Q46: Filmes que saem do ranking IMDb ao elevar o mínimo de votos.
WITH elegiveis AS (
    SELECT m.sk_movie_id, m.titulo, f.nota_imdb, f.qtd_imdb
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE f.nota_imdb BETWEEN 0 AND 10 AND f.qtd_imdb >= 1000
), top_mil AS (
    SELECT * FROM elegiveis ORDER BY nota_imdb DESC, qtd_imdb DESC, titulo, sk_movie_id LIMIT 10
), top_dez_mil AS (
    SELECT * FROM elegiveis WHERE qtd_imdb >= 10000
    ORDER BY nota_imdb DESC, qtd_imdb DESC, titulo, sk_movie_id LIMIT 10
)
SELECT a.titulo, a.nota_imdb, a.qtd_imdb
FROM top_mil a LEFT JOIN top_dez_mil b USING (sk_movie_id)
WHERE b.sk_movie_id IS NULL
ORDER BY a.nota_imdb DESC, a.qtd_imdb DESC, a.titulo, a.sk_movie_id;

-- Q47: Filtrar o ranking anterior de comédias sem repor itens.
WITH ranking AS (
    SELECT m.sk_movie_id, m.titulo, f.nota_imdb, f.qtd_imdb,
           f.receita_brl - f.orcamento_brl AS lucro_brl
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento = 2023 AND g.nome_genero = 'Comedy'
      AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
    ORDER BY lucro_brl DESC, m.titulo, m.sk_movie_id LIMIT 5
)
SELECT titulo, nota_imdb FROM ranking WHERE nota_imdb > 7 AND qtd_imdb > 0
ORDER BY lucro_brl DESC, titulo, sk_movie_id;

-- Q48: Mesmo ranking anterior, trocando comédia por terror.
SELECT m.titulo, f.receita_brl - f.orcamento_brl AS lucro_brl
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.ano_lancamento = 2023 AND g.nome_genero = 'Horror'
  AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
ORDER BY lucro_brl DESC, m.titulo, m.sk_movie_id LIMIT 5;

-- Q49: Mesmo ranking de animações com um novo período.
SELECT m.titulo, f.receita_brl
FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
WHERE m.data_lancamento BETWEEN '2020-01-01' AND DATE('now')
  AND g.nome_genero = 'Animation' AND f.receita_brl IS NOT NULL
ORDER BY f.receita_brl DESC, m.titulo, m.sk_movie_id LIMIT 5;
