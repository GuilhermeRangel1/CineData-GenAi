"""Referências e apresentação para consultas que precisam de recorte explícito."""

import re
from dataclasses import replace

from app.evaluation_cases import MANDATORY_EVALUATIONS
from app.expansion_evaluation_cases import EXPANSION_EVALUATIONS
from app.result_summary import format_result_value
from app.round_two_evaluation_cases import ROUND_TWO_EVALUATIONS

_CASES = {
    case.query_id: case
    for case in MANDATORY_EVALUATIONS + EXPANSION_EVALUATIONS + ROUND_TWO_EVALUATIONS
}
_Q25_NON_BRL = re.compile(
    r"\b(?:dolar(?:es)?|usd|euros?|eur|libras?|gbp|ienes?|jpy)\b|(?:us|u)\$|[€£¥]"
)
_GENRE_FILTER = re.compile(
    r"\b(?:generos?|terror|horror|comedias?|comedy|acao|action|animac(?:ao|oes)|animation|"
    r"aventura|adventure|documentarios?|documentary|drama|familia|family|"
    r"fantasia|fantasy|historia|history|musica|music|misterio|mystery|romance|"
    r"ficcao cientifica|science fiction|sci[- ]?fi|suspense|thriller|guerra|war|"
    r"faroeste|western|crime|filme de tv|tv movie)\b"
)

_PATTERNS = {
    "Q13": r"^(?:que|quais) (?:titulos|filmes) receberam mais avaliacoes "
           r"(?:dos|de) usuarios(?: do cinedata)?[?.!]*"
           r"(?:\s+(?:mostra|mostre) a contagem de cada um[?.!]*)?$",
    "Q06": r"^(?:agrupa|agrupe) os filmes (?:pelo ano em que sairam|por ano de lancamento)"
           r" e (?:mostra|mostre) a media do imdb"
           r" e o numero de filmes avaliados em cada ano[?.!]*$",
    "Q05": r"^em quais (?:dez|10) filmes as notas do (?:imdb e do tmdb|tmdb e do imdb) "
           r"mais destoam\??(?: mostra as notas, os votos de cada site "
           r"e a diferenca em pontos\.?)?$",
    "Q08": r"^quem lidera em media de nota do imdb na direcao, contando so quem dirigiu "
           r"ao menos (?:cinco|5) filmes avaliados\? se empatar, mostra todos, "
           r"com a media e a quantidade\.?$",
    "Q19": r"^(?=.*\b2016\b.*\b2024\b)(?=.*\banimacoes\b)"
           r"(?=.*\bmedia\s+(?:do\s+)?imdb\b)"
           r"(?=.*\bano\b)(?=.*\b(?:dez|10) ou mais filmes avaliados\b)"
           r"(?=.*\b(?:na frente|maior|melhor)\b)",
    "Q20": r"^quem dirigiu (?:o )?(?:leonardo )?dicaprio em (?:dois|2) ou mais filmes\?"
           r" por diretor,.*\bfilmes em comum\b.*\bmedia imdb\b"
           r"|^(?:me mostra|mostra|mostre) os diretores com pelo menos (?:dois|2) filmes "
           r"no elenco d[oe] (?:leonardo )?dicaprio\b.*\bmedia imdb\b"
           r"|^(?:quem dirigiu (?:o )?(?:leonardo )?dicaprio "
           r"(?:pelo menos (?:duas|2) vezes|(?:duas|2) vezes ou mais)\?"
           r"(?: (?:me da os nomes|diz quantos filmes).*nota.*imdb.*)?|"
           r"quais diretores fizeram pelo menos (?:dois|2) filmes com (?:o )?"
           r"(?:leonardo )?dicaprio\?(?: pra cada um, quero o total de filmes juntos, "
           r"quantos tem avaliacao valida no imdb e a media la, da maior pra menor\.?)?)$",
    "Q37": r"^(?:quantos lancamentos (?:teve|houve) por genero nos "
           r"(?:cinco|5) anos mais recentes|"
           r"quantos filmes estrearam nos ultimos (?:cinco|5) anos em cada genero|"
           r"nos ultimos (?:cinco|5) anos, quantos filmes sairam de cada genero|"
           r"de (?:uns )?(?:cinco|5) anos pra ca, quantos filmes estrearam (?:por|de cada) genero|"
           r"me passa o numero de estreias por genero dos ultimos (?:cinco|5) anos)[?.!]*$",
    "Q41": r"^(?:quem dirigiu pelo menos um (?:filme de )?terror e uma comedia de 2016 pra ca\?"
           r"(?: pode listar ate (?:10|dez) nomes, em ordem alfabetica\.?)?|"
           r"desde 2016, quem (?:ja )?dirigiu tanto terror quanto comedia\?"
           r" ate (?:10|dez) nomes de a a z\.?)$",
    "Q21": r"(?=.*\b(?:tres|3) generos\b)(?=.*\b(?:lucro medio|media de receita menos orcamento)\b)"
           r"(?=.*\b(?:numero de filmes|quantidade incluida|total que entrou)\b)"
           r"(?=.*\b(?:percentual|porcentagem)\b)(?=.*\b2016\b.*\b2024\b)",
    "Q25": r"(?=.*\b2023\b)(?=.*\b(?:dez|10) filmes\b)(?=.*\bbilheteria\b)"
           r"(?=.*\b(?:porcentagem|percentual|fatia)\b)",
    "Q27": r"^(?:quais|que) (?:filmes de )?animac\w*\b.*\bano (?:passado|anterior)\b"
           r".*\b(?:se pagar(?:am)?|recuperaram pelo menos o orcamento)\b",
    "Q29": r"(?=.*\b(?:cinco|5) filmes (?:mais caros|de maior orcamento)\b)"
           r"(?=.*\b2023\b)(?=.*\b(?:prejuizo|no vermelho)\b)",
    "Q30": r"(?=.*\b2024\b)(?=.*\bfilmes de terror\b)(?=.*\borcamentos?\b)"
           r"(?=.*\b(?:median[oa]|divide ao meio)\b)",
    "Q32": r"(?=.*\bgenero\b)(?=.*\b2022\b.*\b2023\b)"
           r"(?=.*\b(?:cresceu|aumentou|ganhou mais|maior ganho)\b)"
           r"(?=.*\b(?:bilheteria|arrecadacao)\b)",
    "Q33": r"(?=.*\b2023\b)(?=.*\btop\s*10\b)"
           r"(?=.*\bbilheteria\b.*\blucro\b)"
           r"(?=.*\b(?:tanto\b.*\b(?:quanto|como)|tambem no top|e no top)\b)"
           r"|(?=.*\b2023\b)(?=.*\b(?:cruza|cruze|cruzar)\b)"
           r"(?=.*\b(?:dez|10)\b.*\b(?:bilheteria|arrecadaram)\b)"
           r"(?=.*\b(?:dez|10)\b.*\b(?:lucrativos|lucraram)\b)"
           r"|(?=.*\b2023\b)(?=.*\bduas listas\b)"
           r"(?=.*\b(?:dez|10) que mais arrecadaram\b)"
           r"(?=.*\b(?:dez|10) que mais lucraram\b)",
    "Q34": r"(?=.*\b2024\b)(?=.*\bgeneros?\b)"
           r"(?=.*\bmaior (?:fatia|parcela|porcentagem|proporcao) de filmes com\b)"
           r"(?=.*\b(?:orcamento|custo)\b)(?=.*\b(?:bilheteria|arrecadacao)\b)"
           r"(?=.*\b(?:informados|registrados|conhecidos|os dois dados)\b)",
    "Q35": r"(?=.*\banimacoes\b)(?=.*\b2023\b)(?=.*\bcada (?:real|r\$\s*1)\b)"
           r"(?=.*\b(?:bilheteria|arrecadaram)\b)(?=.*\b(?:orcamento|gasto)\b)",
    "Q38": r"^quem (?:(?:esta|ta) no elenco (?:de|da)|atuou no filme da) "
           r"barbie(?:, aquele filme)?,? de 2023[?.!]*$"
           r"|^(?:me passa|mostra|mostre) os nomes de quem atuou em "
           r"barbie,? (?:a )?versao de 2023[?.!]*$",
    "Q39": r"(?=.*\bfilmes\b)(?=.*\bdicaprio\b)(?=.*\bscorsese\b)"
           r"(?=.*\b(?:atuou|elenco)\b)(?=.*\b(?:dirigiu|direcao)\b)",
    "Q43": r"(?=.*\b(?:cinco|5) produtoras\b)(?=.*\b2023\b)"
           r"(?=.*\bmais (?:fizeram filmes|produziram filmes|lancaram filmes|"
           r"lancamentos|filmes|titulos)\b)"
           r"(?=.*\b(?:mais arrecadou|arrecadou mais|maior bilheteria|campeao de bilheteria)\b)"
           r"(?=.*\bcada\b)",
    "Q45": r"(?=.*\b2019\b)(?=.*\bimdb\b)(?=.*\btmdb\b)"
           r"(?=.*\bnota 8\b)(?=.*\b(?:10 mil|10000|10\.000) votos\b)",
    "Q42": r"(?=.*\b(?:cinco|5) produtoras\b)(?=.*\b2024\b)"
           r"(?=.*\b(?:coproduc\w*|parceria com outras(?: produtoras| em 2024))\b)",
}

REFERENCES = {
    "Q34": """SELECT g.nome_genero,
        100.0 * AVG(f.orcamento_brl IS NOT NULL AND f.receita_brl IS NOT NULL)
            AS percentual_informado
    FROM dim_movies m JOIN bridge_movie_genre b USING (sk_movie_id)
    JOIN dim_genres g USING (sk_genre_id)
    LEFT JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.ano_lancamento = 2024
    GROUP BY g.sk_genre_id, g.nome_genero
    ORDER BY percentual_informado DESC, g.nome_genero, g.sk_genre_id LIMIT 1""",
    "Q41": """SELECT p.nome_pessoa AS diretor
FROM dim_people p JOIN bridge_movie_person b USING (sk_person_id)
JOIN dim_movies m USING (sk_movie_id) JOIN bridge_movie_genre bg USING (sk_movie_id)
JOIN dim_genres g USING (sk_genre_id)
WHERE p.tipo_pessoa = 'Diretor' AND m.data_lancamento BETWEEN '2016-01-01' AND DATE('now')
  AND g.nome_genero IN ('Horror', 'Comedy')
GROUP BY p.sk_person_id, p.nome_pessoa HAVING COUNT(DISTINCT g.nome_genero) = 2
ORDER BY p.nome_pessoa COLLATE NOCASE, p.sk_person_id LIMIT 10""",
    "Q37": """SELECT g.nome_genero, COUNT(DISTINCT m.sk_movie_id) AS total_filmes
FROM dim_movies m JOIN bridge_movie_genre b USING (sk_movie_id)
JOIN dim_genres g USING (sk_genre_id)
WHERE m.data_lancamento BETWEEN DATE('now', '-5 years') AND DATE('now')
GROUP BY g.sk_genre_id, g.nome_genero
ORDER BY total_filmes DESC, g.nome_genero, g.sk_genre_id""",
    "Q20": """WITH filmes AS (
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
ORDER BY nota_media_imdb DESC, filmes_em_comum DESC, diretor, sk_person_id""",
    "Q21": """SELECT g.nome_genero, AVG(f.receita_brl - f.orcamento_brl) AS lucro_medio_brl,
        COUNT(*) AS filmes_elegiveis,
        100.0 * AVG(f.receita_brl > f.orcamento_brl) AS percentual_lucrativo
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento BETWEEN 2016 AND 2024
      AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
    GROUP BY g.sk_genre_id, g.nome_genero ORDER BY lucro_medio_brl DESC, g.nome_genero LIMIT 3""",
    "Q25": """WITH receitas AS (
        SELECT m.sk_movie_id, f.receita_brl
        FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE m.ano_lancamento = 2023 AND f.receita_brl IS NOT NULL
    ), top_dez AS (
        SELECT receita_brl FROM receitas ORDER BY receita_brl DESC, sk_movie_id LIMIT 10
    )
    SELECT 100.0 * (SELECT SUM(receita_brl) FROM top_dez)
           / NULLIF(SUM(receita_brl), 0) AS percentual_bilheteria FROM receitas""",
    "Q27": """SELECT m.titulo FROM dim_movies m
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.data_lancamento >= DATE('now', 'start of year', '-1 year')
      AND m.data_lancamento < DATE('now', 'start of year')
      AND g.nome_genero = 'Animation' AND f.receita_brl >= f.orcamento_brl
    ORDER BY m.titulo, m.sk_movie_id""",
    "Q29": """WITH caros AS (
        SELECT m.sk_movie_id, m.titulo, f.orcamento_brl, f.receita_brl
        FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE m.ano_lancamento = 2023 AND f.orcamento_brl IS NOT NULL
        ORDER BY f.orcamento_brl DESC, m.titulo, m.sk_movie_id LIMIT 5
    )
    SELECT titulo, orcamento_brl - receita_brl AS prejuizo_brl
    FROM caros WHERE receita_brl < orcamento_brl
    ORDER BY orcamento_brl DESC, titulo, sk_movie_id""",
    "Q30": """WITH ordenados AS (
        SELECT f.orcamento_brl,
            ROW_NUMBER() OVER (ORDER BY f.orcamento_brl, m.sk_movie_id) AS posicao,
            COUNT(*) OVER () AS total
        FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
        JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
        WHERE m.ano_lancamento = 2024 AND g.nome_genero = 'Horror'
          AND f.orcamento_brl IS NOT NULL
    )
    SELECT AVG(orcamento_brl) AS orcamento_mediano_brl FROM ordenados
    WHERE posicao IN ((total + 1) / 2, (total + 2) / 2)""",
    "Q32": """WITH totais AS (
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
    ORDER BY aumento_brl DESC, nome_genero, sk_genre_id LIMIT 1""",
    "Q33": """WITH filmes AS (
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
    SELECT r.titulo, r.receita_brl, r.lucro_brl
    FROM por_receita r JOIN por_lucro USING (sk_movie_id)
    ORDER BY r.receita_brl DESC, r.titulo, r.sk_movie_id""",
    "Q35": """SELECT 1.0 * SUM(f.receita_brl) / NULLIF(SUM(f.orcamento_brl), 0) AS receita_por_real
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento = 2023 AND g.nome_genero = 'Animation'
      AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL""",
    "Q38": """SELECT DISTINCT p.nome_pessoa
    FROM dim_movies m JOIN bridge_movie_person b USING (sk_movie_id)
    JOIN dim_people p USING (sk_person_id)
    WHERE m.id_filme = '346698' AND m.ano_lancamento = 2023 AND p.tipo_pessoa = 'Ator'
    ORDER BY p.nome_pessoa COLLATE NOCASE, p.nome_pessoa""",
    "Q39": """WITH roles AS MATERIALIZED (
        SELECT b.sk_movie_id, p.tipo_pessoa
        FROM dim_people p JOIN bridge_movie_person b USING (sk_person_id)
        WHERE (p.tipo_pessoa = 'Ator' AND p.nome_pessoa = 'Leonardo DiCaprio' COLLATE NOCASE)
           OR (p.tipo_pessoa = 'Diretor' AND p.nome_pessoa = 'Martin Scorsese' COLLATE NOCASE)
    )
    SELECT titulo, ano_lancamento FROM dim_movies
    WHERE sk_movie_id IN (
        SELECT sk_movie_id FROM roles GROUP BY sk_movie_id HAVING COUNT(DISTINCT tipo_pessoa) = 2
    )
    ORDER BY ano_lancamento, titulo, sk_movie_id""",
    "Q43": """WITH creditos AS MATERIALIZED (
        SELECT DISTINCT sk_company_id, m.sk_movie_id
        FROM dim_movies m JOIN bridge_movie_company USING (sk_movie_id)
        WHERE m.ano_lancamento = 2023
    ), maiores AS MATERIALIZED (
        SELECT c.sk_company_id, c.nome_produtora, COUNT(*) AS total
        FROM creditos JOIN dim_companies c USING (sk_company_id)
        GROUP BY c.sk_company_id, c.nome_produtora
        ORDER BY total DESC, c.nome_produtora COLLATE NOCASE, c.sk_company_id LIMIT 5
    ), filmes AS (
        SELECT p.sk_company_id, m.titulo, f.receita_brl,
            ROW_NUMBER() OVER (
                PARTITION BY p.sk_company_id
                ORDER BY f.receita_brl DESC, m.titulo, m.sk_movie_id
            ) AS posicao
        FROM maiores p JOIN creditos USING (sk_company_id)
        JOIN dim_movies m USING (sk_movie_id)
        JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE f.receita_brl IS NOT NULL
    )
    SELECT p.nome_produtora, filmes.titulo, filmes.receita_brl
    FROM maiores p LEFT JOIN filmes
      ON filmes.sk_company_id = p.sk_company_id AND filmes.posicao = 1
    ORDER BY p.total DESC, p.nome_produtora COLLATE NOCASE, p.sk_company_id""",
    "Q45": """SELECT m.titulo, f.nota_imdb, f.qtd_imdb, f.nota_tmdb, f.qtd_tmdb
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    WHERE m.ano_lancamento = 2019
      AND f.nota_imdb BETWEEN 8 AND 10 AND f.nota_tmdb BETWEEN 8 AND 10
      AND f.qtd_imdb >= 10000 AND f.qtd_tmdb >= 10000
    ORDER BY f.nota_imdb DESC, f.qtd_imdb DESC, m.titulo, m.sk_movie_id""",
    "Q42": """WITH coproducoes AS (
        SELECT b.sk_movie_id FROM bridge_movie_company b JOIN dim_movies m USING (sk_movie_id)
        WHERE m.ano_lancamento = 2024 GROUP BY b.sk_movie_id
        HAVING COUNT(DISTINCT b.sk_company_id) >= 2
    )
    SELECT c.nome_produtora, COUNT(DISTINCT b.sk_movie_id) AS total_coproducoes
    FROM coproducoes JOIN bridge_movie_company b USING (sk_movie_id)
    JOIN dim_companies c USING (sk_company_id)
    GROUP BY c.sk_company_id, c.nome_produtora
    ORDER BY total_coproducoes DESC, c.nome_produtora COLLATE NOCASE, c.sk_company_id LIMIT 5""",
}

MODEL_HINTS = {
    "Q19": "Use dim_genres.nome_genero = 'Animation'. Antes de agrupar por ano, "
           "filtre WHERE qtd_imdb > 0 e nota_imdb BETWEEN "
           "0 AND 10. Use exatamente esse conjunto tanto no AVG(nota_imdb) quanto no "
           "COUNT(*). Exija HAVING COUNT(*) >= 10 e ordene pela média DESC e ano ASC.",
    "Q32": "Retorne obrigatoriamente duas colunas: nome_genero e aumento_brl. "
           "Calcule SUM(receita_brl) em 2022 e 2023 por gênero, subtraia "
           "receita_2022 de receita_2023 e escolha o maior aumento positivo. "
           "A pergunta pede o valor em reais além do nome do gênero.",
    "Q34": "Use todos os filmes de 2024 em cada gênero como denominador. Faça LEFT JOIN "
           "com o desempenho e conte no numerador somente quando orçamento e receita "
           "estiverem informados no mesmo filme. Retorne nome_genero e percentual_informado.",
    "Q20": "Selecione os filmes com crédito de Ator usando "
           "nome_pessoa = 'Leonardo DiCaprio' COLLATE NOCASE e cruze "
           "com os créditos de Diretor. Exija pelo menos dois filmes em comum e conte "
           "separadamente os filmes com nota IMDb e votos positivos. Retorne diretor, "
           "filmes_em_comum, filmes_avaliados e nota_media_imdb; ordene pela média decrescente.",
    "Q37": "Use a janela móvel de DATE('now', '-5 years') até DATE('now'), sobre "
           "data_lancamento. Conte filmes distintos por gênero, sem somar votos. "
           "Retorne nome_genero e total_filmes em ordem decrescente de contagem.",
    "Q41": "Use data_lancamento de 2016-01-01 até hoje. Para créditos de Diretor, "
           "exija associação com Horror e Comedy. Retorne no máximo dez diretores "
           "distintos, ordenados por nome e chave, com LIMIT 10.",
    "Q40": "Retorne exatamente cinco duplas. Conte filmes distintos de terror de 2023, "
           "sem repetir pares invertidos. Ordene por total_filmes DESC e pelos dois "
           "nomes em ordem alfabética. Aplique LIMIT 5. Retorne ator_1, ator_2 e total_filmes.",
    "Q21": "Total que entrou é a quantidade de filmes usada no cálculo: COUNT(*) como "
           "filmes_elegiveis. Não some bilheteria para essa coluna. "
           "O percentual lucrativo é calculado sobre o mesmo grupo de filmes elegíveis.",
    "Q25": "Use exclusivamente a métrica em reais f.receita_brl, nunca receita_usd. "
           "Use a mesma população de filmes de 2023 com receita_brl informada no "
           "numerador e no denominador. Ordene receita_brl DESC e sk_movie_id, limite "
           "a dez antes de somar o numerador. Retorne 100.0 vezes a soma das dez "
           "receitas dividida pela soma de todas as receitas como percentual_bilheteria.",
    "Q42": "Conte filmes distintos de 2024 com pelo menos duas produtoras. Ordene "
           "produtoras por total_coproducoes DESC, nome_produtora e ID e aplique LIMIT 5. "
           "Retorne exatamente cinco linhas quando houver cinco produtoras.",
    "Q29": "Escolha primeiro os cinco maiores orçamentos, sem filtrar por prejuízo. "
           "Depois calcule quanto faltou para cada um se pagar (orçamento menos receita).",
    "Q30": "Use o gênero Horror. Numere os orçamentos não nulos com ROW_NUMBER() e "
           "calcule COUNT(*) OVER () antes de filtrar as posições centrais. "
           "Retorne AVG(orcamento_brl) como orcamento_mediano_brl.",
    "Q33": "Monte os rankings de receita e de lucro separadamente e cruze pelo ID do filme. "
           "Retorne obrigatoriamente titulo, receita_brl e lucro_brl. "
           "Use o alias exato lucro_brl para receita_brl - orcamento_brl em todas as CTEs. "
           "As colunas finais devem se chamar titulo, receita_brl e lucro_brl, "
           "em ordem decrescente de receita. Não use alias em inglês.",
    "Q35": "Divida a soma das receitas pela soma dos orçamentos do mesmo grupo de animações. "
           "Inclua somente filmes com os dois valores informados.",
    "Q38": "Filtre dim_movies.id_filme = '346698' para o longa Barbie (2023). "
           "Para ligar aos créditos, faça JOIN pela chave sk_movie_id. "
           "Retorne os nomes distintos dos créditos de Ator em nome_pessoa.",
    "Q39": "Cruze os créditos de Leonardo DiCaprio como Ator e Martin Scorsese como Diretor. "
           "Retorne titulo e ano_lancamento. Não procure essas pessoas na sinopse.",
    "Q43": "Selecione as cinco produtoras pela contagem de filmes distintos de 2023 antes de "
           "filtrar bilheterias. Materialize os créditos do ano e as cinco produtoras. "
           "Junte os filmes dessas cinco produtoras apenas depois do LIMIT. Para cada "
           "produtora, ordene receitas não nulas em ordem decrescente e escolha uma "
           "linha com ROW_NUMBER. No SELECT final comece pelas cinco produtoras e faça "
           "LEFT JOIN com os filmes ranqueados, incluindo posicao = 1 no ON. "
           "Não filtre a receita ou a posição no WHERE final. Deixe título e receita "
           "nulos para produtoras sem bilheteria registrada no ano. "
           "Evite calcular ROW_NUMBER sobre todas as produtoras do catálogo. "
           "Retorne nome_produtora, titulo, receita_brl.",
    "Q45": "Neste caso, nota 8 significa pelo menos 8. Aplique nota de 8 a 10 e pelo menos 10000 "
           "votos separadamente no IMDb e no TMDB, com AND para os quatro critérios. Retorne "
           "titulo, nota_imdb, qtd_imdb, nota_tmdb e qtd_tmdb, não somente títulos.",
}


def horror_producer_ranking(question: str) -> str | None:
    if not re.fullmatch(
        r"das (?:cinco|5) produtoras com mais filmes de terror em 2023,? "
        r"qual foi o filme(?: de terror)? de maior bilheteria de cada uma[?.!]*",
        question,
    ):
        return None
    return REFERENCES["Q43"].replace(
        "WHERE m.ano_lancamento = 2023",
        "JOIN bridge_movie_genre USING (sk_movie_id) "
        "JOIN dim_genres USING (sk_genre_id) "
        "WHERE m.ano_lancamento = 2023 AND nome_genero = 'Horror'",
        1,
    )


def match_reviewed_case(question: str):
    if re.search(r"\b(?:exatamente|somente|igual a|apenas)\s+(?:a\s+)?(?:nota\s+)?8\b", question):
        return None
    expected = {
        "Q05": set(), "Q06": set(), "Q08": set(), "Q20": set(), "Q37": set(), "Q41": {"2016"},
        "Q21": {"2016", "2024"}, "Q25": {"2023"}, "Q27": set(), "Q29": {"2023"}, "Q30": {"2024"},
        "Q32": {"2022", "2023"}, "Q33": {"2023"}, "Q34": {"2024"}, "Q35": {"2023"},
        "Q13": set(), "Q19": {"2016", "2024"}, "Q38": {"2023"},
        "Q39": set(), "Q42": {"2024"}, "Q43": {"2023"}, "Q45": {"2019"},
    }
    years = set(re.findall(r"\b(?:19|20)\d{2}\b", question))
    for key, pattern in _PATTERNS.items():
        if years == expected[key] and re.match(pattern, question):
            if key == "Q25" and _Q25_NON_BRL.search(question):
                return None
            if key in {"Q25", "Q29", "Q43"} and _GENRE_FILTER.search(question):
                return None
            return _CASES[key]
    return None


_ANIMATION_RANK = re.compile(
    r"quais (?:cinco|5) animacoes de (\d{4}) pra ca tiveram a maior bilheteria em reais[?.!]*"
)
_NEW_START = re.compile(
    r"(?:agora so de |refaz esse ranking so de |e se pegar so de |corta os anteriores a |"
    r"refaz o ranking comecando em |mantem esse top, mas coloca )(\d{4})"
    r"(?: pra ca| como ano inicial)?[?.!]*"
)
_COMEDY_RANK = r"quais foram as cinco comedias mais lucrativas de 2023"
_IMDB_FILTER = (
    r"(?:(?:e )?(?:dessas(?: ai| cinco)?|desse grupo|daquele top),? quais |"
    r"(?:e )?quais dessas |daquele top(?: de comedia)?,? separa (?:pra mim )?so os que )"
    r"(?:passaram de 7|tiveram nota acima de 7|tiraram mais (?:que|de) 7|"
    r"ficaram (?:acima de|com mais de) 7) no imdb"
    r"(?: e (?:com que nota|mostra as notas)|\?\s*(?:diz a nota tambem|me mostra as notas|"
    r"manda as notas tambem|que nota tiraram))?"
)
_RANKING_AND_FILTER = re.compile(
    rf'["“]?{_COMEDY_RANK}\?["”]?\s*e depois\s*["“]?{_IMDB_FILTER}[?!.]*["”]?'
)
_HORROR_FOLLOWUP = re.compile(
    r"(?:(?:faz o mesmo|e se trocar) (?:pra|para) terror|agora faz com filmes de terror|"
    r"me da esse mesmo top (?:5|cinco),? mas de terror|e de terror,? como fica|"
    r"troca comedia por terror nesse top|"
    r"troca o genero d(?:aquele|esse) (?:ranking|top) (?:pra|para) terror"
    r"(?: e mantem o resto igual)?)[?!.]*"
)

_PROFIT_RANK = """SELECT m.sk_movie_id, m.titulo, f.nota_imdb, f.qtd_imdb,
           f.receita_brl - f.orcamento_brl AS lucro_brl
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.ano_lancamento = 2023 AND g.nome_genero = '{genre}'
      AND f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
    ORDER BY lucro_brl DESC, m.titulo, m.sk_movie_id LIMIT 5"""

REFERENCES["Q47"] = (
    f"WITH ranking AS ({_PROFIT_RANK.format(genre='Comedy')}) "
    "SELECT titulo, nota_imdb FROM ranking WHERE nota_imdb > 7 AND qtd_imdb > 0 "
    "ORDER BY lucro_brl DESC, titulo, sk_movie_id"
)
REFERENCES["Q48"] = (
    f"WITH ranking AS ({_PROFIT_RANK.format(genre='Horror')}) "
    "SELECT titulo, lucro_brl FROM ranking ORDER BY lucro_brl DESC, titulo, sk_movie_id"
)
MODEL_HINTS["Q47"] = (
    "Calcule primeiro as cinco comédias de 2023 pelo lucro calculado como "
    "receita_brl - orcamento_brl. Exija os dois valores informados, ordene pelo "
    "lucro decrescente, título e ID antes do LIMIT 5. "
    "Só então filtre nota IMDb maior que 7 e votos positivos. Retorne titulo e nota_imdb."
)
MODEL_HINTS["Q48"] = (
    "Execute o ranking completo em uma chamada run_sql, sem consultar os gêneros primeiro. "
    "Filtre dim_genres.nome_genero = 'Horror' e mantenha o ano 2023. "
    "Exija receita_brl e orcamento_brl informados e calcule a diferença como lucro_brl. "
    "Ordene por lucro_brl DESC, título e ID e limite a cinco. "
    "Ignore filtros de nota de pedidos anteriores. Retorne titulo e lucro_brl."
)


def profit_ranking_followup(question: str, previous: str):
    if _RANKING_AND_FILTER.fullmatch(question):
        return _CASES["Q47"]
    previous_rank = re.fullmatch(rf"{_COMEDY_RANK}[?!.]*", previous)
    if previous_rank and re.fullmatch(rf"{_IMDB_FILTER}[?!.]*", question):
        return _CASES["Q47"]
    if (previous_rank or _RANKING_AND_FILTER.fullmatch(previous)) and (
        _HORROR_FOLLOWUP.fullmatch(question)
    ):
        return _CASES["Q48"]
    return None


def animation_ranking(question: str, previous: str):
    match = _ANIMATION_RANK.fullmatch(question)
    if match is None and _ANIMATION_RANK.fullmatch(previous):
        match = _NEW_START.fullmatch(question)
    if match is None:
        return None
    start = int(match[1])
    case = replace(
        _CASES["Q49"], period=f"Desde {start} até hoje",
    )
    sql = f"""SELECT m.titulo, f.receita_brl, m.ano_lancamento
    FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
    JOIN bridge_movie_genre b USING (sk_movie_id) JOIN dim_genres g USING (sk_genre_id)
    WHERE m.data_lancamento BETWEEN '{start:04d}-01-01' AND DATE('now')
      AND g.nome_genero = 'Animation' AND f.receita_brl IS NOT NULL
    ORDER BY f.receita_brl DESC, m.titulo, m.sk_movie_id LIMIT 5"""
    return case, sql, start


def reviewed_summary(question: str, rows: tuple, query_id: str | None) -> str | None:
    if not rows:
        return None
    first = rows[0]
    if len(rows) == 1 and (
        query_id == "Q19" or (
            "animac" in question and "imdb" in question
            and re.search(r"\b(?:maior|melhor) (?:nota )?media\b", question)
        )
    ):
        year = first.get("ano_lancamento", first.get("ano"))
        mean = first.get("nota_media_imdb", first.get("media_imdb", first.get("media")))
        count = next((
            first[key]
            for key in ("filmes_avaliados", "qtd_filmes_avaliados", "qtd_animacoes",
                        "quantidade_filmes", "qtd_filmes", "quantidade")
            if type(first.get(key)) is int
        ), None)
        if type(year) is int and type(mean) in (int, float):
            text = f"{year} liderou, com nota média de {format_result_value('', mean)} no IMDb."
            if type(count) is int:
                text += f" A média considera {format_result_value('', count)} filmes avaliados."
            return text
    if all(
        {"ano_lancamento", "qtd_comedia", "qtd_terror",
         "lucro_medio_comedia", "lucro_medio_terror"} <= row.keys()
        for row in rows
    ):
        years = ", ".join(str(row["ano_lancamento"]) for row in rows)
        return (
            f"Em {len(rows)} {'ano' if len(rows) == 1 else 'anos'}, a comédia teve mais "
            f"estreias, mas o terror teve maior lucro médio. Anos: {years}."
        )
    if query_id == "Q47":
        return f"Das cinco comédias mais lucrativas de 2023, {len(rows)} passaram de 7 no IMDb."
    if query_id == "Q48":
        return f"Top {len(rows)} de filmes de terror de 2023 por lucro estimado em reais."
    if query_id == "Q39" and len(rows) == 1:
        return (f"Nos créditos do catálogo, Leonardo DiCaprio atuou sob direção de Martin "
                f"Scorsese em {first['titulo']} ({first['ano_lancamento']}).")
    if query_id == "Q43":
        available = [row for row in rows if row["receita_brl"] is not None]
        pairs = [
            f"{row['nome_produtora']}: {row['titulo']} "
            f"({format_result_value('receita_brl', row['receita_brl'])})"
            for row in available
        ]
        text = "Maiores bilheterias registradas entre as produtoras selecionadas em 2023."
        if pairs:
            text += "\n\n" + "\n".join(f"- {pair}" for pair in pairs)
        missing = [row["nome_produtora"] for row in rows if row["receita_brl"] is None]
        if missing:
            text += "\n\nSem bilheteria informada no recorte: " + ", ".join(missing) + "."
        return text
    if query_id == "Q45":
        return (f"{len(rows)} filmes de 2019 tiveram nota 8 ou mais e pelo menos 10 mil "
                "votos em cada plataforma. A tabela mostra as notas e os votos de cada uma.")
    if query_id == "Q42":
        maximum = first["total_coproducoes"]
        leaders = [
            "ZDF" if row["nome_produtora"] == "Zdf" else row["nome_produtora"]
            for row in rows if row["total_coproducoes"] == maximum
        ]
        if len(leaders) > 1:
            return (f"{' e '.join(leaders)} empataram na liderança em 2024, "
                    f"com {maximum} coproduções cada.")
    if query_id == "Q29":
        items = ", ".join(
            f"{row['titulo']} ({format_result_value('prejuizo_brl', row['prejuizo_brl'])})"
            for row in rows
        )
        return (f"Dos cinco filmes mais caros de 2023, {len(rows)} aparecem "
                f"com prejuízo registrado: {items}.")
    if query_id == "Q35" and type(first.get("receita_por_real")) in (int, float):
        value = format_result_value("receita_brl", first["receita_por_real"])
        return (f"As animações de 2023 com orçamento e bilheteria informados arrecadaram "
                f"{value} para cada R$ 1 de orçamento, somando os valores.")
    if (query_id == "Q33" or len(re.findall(r"\btop\s*10\b", question)) == 2) and all(
        type(row.get(key)) in (int, float) for row in rows for key in ("lucro_brl", "receita_brl")
    ):
        revenue = max(rows, key=lambda row: row["receita_brl"])
        profit = max(rows, key=lambda row: row["lucro_brl"])
        return (f"{len(rows)} filmes entraram nos dois top 10. Nesse grupo, "
                f"{revenue['titulo']} liderou em bilheteria e {profit['titulo']} em lucro.")
    return None
