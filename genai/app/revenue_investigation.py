"""Investiga mudanças anuais de bilheteria registradas no Gold."""

import re
from math import isclose

from app.agent_models import AgentResponse
from app.result_summary import format_result_value, genre_label
from app.sql_executor import GoldQueryExecutor
from app.sql_guard import validate_sql

_GENRES = {
    "animacao": "Animation", "animacoes": "Animation",
    "terror": "Horror", "comedia": "Comedy", "comedias": "Comedy",
    "acao": "Action", "ficcao cientifica": "Science Fiction",
}


def revenue_growth_context(
    question: str, genre: str, increase: float, executor: GoldQueryExecutor, max_rows: int,
) -> tuple[str, ...]:
    """Mostra as bases do aumento de bilheteria informado para um gênero."""
    years = re.findall(r"\b(?:19|20)\d{2}\b", question)
    if len(years) != 2 or years[0] >= years[1]:
        return ()
    start, end = (int(year) for year in years)
    genre_literal = genre.replace("'", "''")
    sql = f"""
        SELECT m.ano_lancamento, COUNT(f.receita_brl) AS filmes_com_receita,
               SUM(f.receita_brl) AS receita_brl
        FROM dim_movies m
        JOIN bridge_movie_genre b USING (sk_movie_id)
        JOIN dim_genres g USING (sk_genre_id)
        JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE m.ano_lancamento IN ({start}, {end})
          AND g.nome_genero = '{genre_literal}'
          AND f.receita_brl IS NOT NULL
        GROUP BY m.ano_lancamento
        ORDER BY m.ano_lancamento
    """
    result = executor.execute(validate_sql(sql, max_rows=max_rows))
    if len(result.rows) != 2:
        return ()
    before, after = result.rows
    start_amount = before["receita_brl"]
    end_amount = after["receita_brl"]
    if not isclose(end_amount - start_amount, increase, rel_tol=0, abs_tol=0.01):
        return ()
    growth = ""
    if 0 < start_amount < end_amount:
        percentage = 100 * (end_amount - start_amount) / start_amount
        growth = f" Isso equivale a uma alta de {format_result_value('', percentage)}%."
    return (
        f"No gênero {genre_label(genre)}, a bilheteria registrada foi de "
        f"{format_result_value('receita_brl', start_amount)} em {start} "
        f"({before['filmes_com_receita']} filmes com dados) e "
        f"{format_result_value('receita_brl', end_amount)} em {end} "
        f"({after['filmes_com_receita']} filmes com dados).{growth}",
    )


def finance_coverage_context(
    question: str, executor: GoldQueryExecutor, max_rows: int,
) -> tuple[str, ...]:
    """Distingue ausência de registros e ausência de filmes que se pagaram."""
    animation = bool(
        re.fullmatch(
            r"(?:quais|que|das) (?:filmes de )?animac[a-z]+\b.*\bano (?:passado|anterior)\b"
            r".*\b(?:pagar(?:am)?|recuperaram|empataram)\b.*",
            question,
        )
    )
    action = bool(
        re.fullmatch(
            r"(?:quais|que|dos|me mostra os) filmes de acao\b.*\b(?:neste|este|esse) ano\b"
            r".*\b(?:custo|orcamento)\b.*",
            question,
        )
    )
    if not (animation or action) or re.search(r"\b(?:imdb|tmdb|nota|votos)\b", question):
        return ()
    genre = "Animation" if animation else "Action"
    dates = (
        "m.data_lancamento >= DATE('now','start of year','-1 year') "
        "AND m.data_lancamento < DATE('now','start of year')"
        if animation else "m.data_lancamento BETWEEN DATE('now','start of year') AND DATE('now')"
    )
    sql = f"""
        SELECT CAST(STRFTIME('%Y', DATE('now', 'start of year', '-1 year'))
                    AS INTEGER) AS ano_anterior,
               COUNT(*) AS total,
               COUNT(CASE WHEN f.receita_brl IS NOT NULL AND f.orcamento_brl IS NOT NULL
                          THEN 1 END) AS completos,
               COUNT(CASE WHEN f.receita_brl >= f.orcamento_brl THEN 1 END) AS se_pagaram
        FROM dim_movies m
        LEFT JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE {dates}
          AND EXISTS (
              SELECT 1 FROM bridge_movie_genre b JOIN dim_genres g USING (sk_genre_id)
              WHERE b.sk_movie_id = m.sk_movie_id AND g.nome_genero = '{genre}'
          )
    """
    result = executor.execute(validate_sql(sql, max_rows=max_rows))
    if not result.rows:
        return ()
    total, complete, break_even = (
        result.rows[0][key] for key in ("total", "completos", "se_pagaram")
    )
    if not total:
        if animation and (year := result.rows[0].get("ano_anterior")):
            return (f"Não há estreias de animação registradas no banco de dados em {year}. "
                    "Por isso, não há filmes para avaliar pelo ponto de equilíbrio.",)
        return ("Não há lançamentos desse gênero registrados no banco de dados no período.",)
    if not complete:
        return (
            f"O banco de dados registra {format_result_value('', total)} lançamentos do gênero, "
            "mas nenhum tem orçamento e bilheteria informados juntos.",
        )
    if animation and not break_even:
        return (
            f"Dos {format_result_value('', total)} lançamentos, só "
            f"{format_result_value('', complete)} têm orçamento e bilheteria informados. "
            "Nenhum desses recuperou o orçamento.",
        )
    return ()


def animation_rating_context(
    question: str, year: int, mean: float, executor: GoldQueryExecutor, max_rows: int,
) -> tuple[str, ...]:
    """Confere a amostra de uma média exibida sem a contagem de filmes."""
    if not (1900 <= year <= 2099 and "animac" in question and "imdb" in question):
        return ()
    sql = f"""
        SELECT AVG(f.nota_imdb) AS media, COUNT(*) AS avaliados
        FROM dim_movies m
        JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE m.ano_lancamento = {year}
          AND f.qtd_imdb > 0 AND f.nota_imdb BETWEEN 0 AND 10
          AND EXISTS (
              SELECT 1 FROM bridge_movie_genre b JOIN dim_genres g USING (sk_genre_id)
              WHERE b.sk_movie_id = m.sk_movie_id AND g.nome_genero = 'Animation'
          )
    """
    result = executor.execute(validate_sql(sql, max_rows=max_rows))
    if not result.rows:
        return ()
    check = result.rows[0]
    if check["media"] is None or not isclose(mean, check["media"], rel_tol=0, abs_tol=0.005):
        return ()
    return (
        f"A média de {year} considera {format_result_value('', check['avaliados'])} "
        "animações com nota e votos registrados no IMDb.",
    )


def rating_context_for_titles(
    question: str, rows: tuple[dict, ...], executor: GoldQueryExecutor, max_rows: int,
) -> tuple[dict, ...]:
    """Recupera evidências para rankings que exibem apenas títulos."""
    if not 2 <= len(rows) <= 10 or not all(
        isinstance(row.get("titulo"), str) for row in rows
    ) or "imdb" not in question:
        return ()
    titles = {row["titulo"] for row in rows}
    if len(titles) != len(rows):
        return ()
    labels = ", ".join("'" + t.replace("'", "''") + "'" for t in sorted(titles))
    years = re.findall(r"\b(?:19|20)\d{2}\b", question)
    if "document" in question and len(years) == 2 and "mil votos" in question:
        start, end = sorted(int(year) for year in years)
        filter_sql = f"""
            AND m.ano_lancamento BETWEEN {start} AND {end}
            AND f.qtd_imdb >= 1000
            AND EXISTS (
                SELECT 1 FROM bridge_movie_genre b JOIN dim_genres g USING (sk_genre_id)
                WHERE b.sk_movie_id = m.sk_movie_id AND g.nome_genero = 'Documentary'
            )
        """
        tmdb = ""
    elif "tmdb" in question and "5 mil votos" in question and "um ponto" in question:
        filter_sql = """
            AND f.qtd_imdb >= 5000 AND f.qtd_tmdb > 0
            AND f.nota_imdb - f.nota_tmdb >= 1
        """
        tmdb = ", f.nota_tmdb"
    else:
        return ()
    sql = f"""
        SELECT m.titulo, f.nota_imdb {tmdb}
        FROM dim_movies m JOIN fact_movies_performance f USING (sk_movie_id)
        WHERE m.titulo IN ({labels})
          AND f.nota_imdb BETWEEN 0 AND 10
          {filter_sql}
    """
    result = executor.execute(validate_sql(sql, max_rows=max_rows))
    lookup = {row["titulo"]: row for row in result.rows}
    if result.truncated or len(result.rows) != len(titles) or lookup.keys() != titles:
        return ()
    return tuple(lookup[row["titulo"]] for row in rows)


def investigate_revenue(
    question: str, executor: GoldQueryExecutor, max_rows: int
) -> AgentResponse | None:
    years = re.findall(r"\b(?:19|20)\d{2}\b", question)
    if len(set(years)) != 2 or not (
        re.search(r"\b(?:bilheteria|arrecadacao)\b", question)
        and re.search(r"\b(?:por que|o que mais contribuiu|o que explica)\b", question)
        and re.search(r"\b(?:alta|subiu|cresceu|aumentou|aumento)\b", question)
    ):
        return None
    start, end = sorted({int(year) for year in years})
    genres = {
        label for term, label in _GENRES.items()
        if re.search(rf"\b{term}\b", question)
    }
    # Accept a single genre or the catalogue total. Other filters go through the agent.
    if len(genres) > 1:
        return None
    genre_filter = ""
    if genres:
        genre = next(iter(genres))
        genre_filter = f"""
            AND EXISTS (
                SELECT 1 FROM bridge_movie_genre b
                JOIN dim_genres g USING (sk_genre_id)
                WHERE b.sk_movie_id = m.sk_movie_id AND g.nome_genero = '{genre}'
            )
        """
    elif not re.search(r"\b(?:total|geral|catalogo)\b", question):
        return None
    if re.search(r"\b(?:imdb|tmdb|orcamento|nota|diretor|produtora|pais|idioma)\b", question):
        return None

    sql = f"""
        WITH filmes AS (
            SELECT m.ano_lancamento, m.sk_movie_id, f.receita_brl,
                   ROW_NUMBER() OVER (
                       PARTITION BY m.ano_lancamento
                       ORDER BY f.receita_brl DESC, m.sk_movie_id
                   ) AS posicao
            FROM dim_movies m
            LEFT JOIN fact_movies_performance f USING (sk_movie_id)
            WHERE m.ano_lancamento IN ({start}, {end})
              AND m.data_lancamento <= DATE('now')
              {genre_filter}
        )
        SELECT ano_lancamento, COUNT(*) AS total_filmes,
               COUNT(receita_brl) AS filmes_com_receita,
               SUM(receita_brl) AS receita_brl,
               AVG(receita_brl) AS receita_media_brl,
               SUM(CASE WHEN posicao <= 3 THEN receita_brl END) AS receita_top_3_brl
        FROM filmes
        GROUP BY ano_lancamento
        ORDER BY ano_lancamento
    """
    result = executor.execute(validate_sql(sql, max_rows=max_rows))
    insights: tuple[str, ...] = ()
    answer = "A bilheteria informada é insuficiente para comparar os dois anos."
    if len(result.rows) == 2:
        before, after = result.rows
        if before["filmes_com_receita"] and after["filmes_com_receita"]:
            delta = after["receita_brl"] - before["receita_brl"]
            def money(value: float) -> str:
                return format_result_value("receita_brl", value)
            if delta > 0:
                answer = f"A bilheteria informada aumentou {money(delta)} de {start} para {end}."
            elif delta < 0:
                answer = f"A bilheteria informada caiu {money(-delta)} de {start} para {end}."
            else:
                answer = f"A bilheteria informada foi igual em {start} e {end}."
            top_delta = after["receita_top_3_brl"] - before["receita_top_3_brl"]
            rest_delta = delta - top_delta
            def describe_change(value: float) -> str:
                if value == 0:
                    return "ficou estável"
                direction = "subiu" if value > 0 else "caiu"
                return f"{direction} {money(abs(value))}"

            answer += (
                f" A receita somada dos três maiores de cada ano {describe_change(top_delta)}."
                f" Entre os demais filmes com bilheteria registrada, a receita "
                f"{describe_change(rest_delta)}."
            )
            insights = (
                f"Os filmes com bilheteria informada passaram de {before['filmes_com_receita']} "
                f"de {before['total_filmes']} para {after['filmes_com_receita']} de "
                f"{after['total_filmes']}. A média por filme com dado passou de "
                f"{money(before['receita_media_brl'])} para {money(after['receita_media_brl'])}.",
            )
    return AgentResponse(
        answer=answer,
        rows=result.rows,
        columns=result.columns,
        truncated=result.truncated,
        tool_calls=1,
        metric="variação da bilheteria anual",
        period=f"{start} e {end}",
        unit="BRL",
        limitations=(
            "a comparação usa a bilheteria registrada no catálogo e não identifica causas externas"
        ),
        insights=insights,
    )


def investigate_profit_or_rating(
    question: str, executor: GoldQueryExecutor, max_rows: int,
) -> AgentResponse | None:
    """Compara as bases e a distribuição da métrica em duas safras de filmes."""
    match = re.fullmatch(
        r"(?:o que explica a (?:mudanca|diferenca) "
        r"(?:no lucro total|na nota media (?:do|no) imdb)"
        r"|por que (?:mudou|subiu|caiu) "
        r"(?:o lucro total|a nota media (?:do|no) imdb))"
        r" (?:dos filmes do catalogo|dos filmes de ([a-z ]+))"
        r" entre ((?:19|20)\d{2}) e ((?:19|20)\d{2})\??",
        question.strip(),
    )
    if match is None:
        return None
    genre_term, start, end = match.groups()
    if start == end or (genre_term and genre_term not in _GENRES):
        return None
    start, end = sorted((int(start), int(end)))
    genre_filter = ""
    if genre_term:
        genre_filter = (
            "AND EXISTS (SELECT 1 FROM bridge_movie_genre b JOIN dim_genres g USING (sk_genre_id) "
            f"WHERE b.sk_movie_id = m.sk_movie_id AND g.nome_genero = '{_GENRES[genre_term]}')"
        )
    profit = "lucro total" in question
    value = (
        "f.receita_brl - f.orcamento_brl" if profit
        else "CASE WHEN f.qtd_imdb > 0 AND f.nota_imdb BETWEEN 0 AND 10 THEN f.nota_imdb END"
    )
    metric_column = "lucro_brl" if profit else "nota_media_imdb"
    total = "SUM" if profit else "AVG"
    category = "filmes_lucrativos" if profit else "filmes_com_nota_oito_ou_mais"
    threshold = "valor > 0" if profit else "valor >= 8"
    sql = f"""
        WITH filmes AS (
            SELECT m.ano_lancamento, {value} AS valor
            FROM dim_movies m
            LEFT JOIN fact_movies_performance f USING (sk_movie_id)
            WHERE m.ano_lancamento IN ({start}, {end})
              AND m.data_lancamento <= DATE('now')
              {genre_filter}
        )
        SELECT ano_lancamento, COUNT(*) AS total_filmes, COUNT(valor) AS filmes_elegiveis,
               {total}(valor) AS {metric_column},
               SUM(CASE WHEN {threshold} THEN 1 ELSE 0 END) AS {category}
        FROM filmes GROUP BY ano_lancamento ORDER BY ano_lancamento
    """
    result = executor.execute(validate_sql(sql, max_rows=max_rows))
    label = "lucro total" if profit else "nota média simples no IMDb"
    answer = "Não há dados suficientes no banco de dados para comparar os dois anos nesse recorte."
    insights: tuple[str, ...] = ()
    if len(result.rows) == 2:
        before, after = result.rows
        a, b = before[metric_column], after[metric_column]
        if a is not None and b is not None:
            delta = b - a
            amount = format_result_value(metric_column, abs(delta))
            if not profit:
                amount += " ponto" if round(abs(delta), 2) == 1 else " pontos"
            if not profit and 0 < abs(delta) < 0.005:
                movement = "variou menos de 0,01 ponto"
            else:
                direction = "subiu" if delta > 0 else "caiu"
                movement = f"{direction} {amount}" if delta else "ficou igual"
            article = "o" if profit else "a"
            answer = f"Pelos dados registrados, {article} {label} {movement} entre {start} e {end}."
            n0, n1 = before["filmes_elegiveis"], after["filmes_elegiveis"]
            share0 = format_result_value("", 100 * before[category] / n0)
            share1 = format_result_value("", 100 * after[category] / n1)
            detail = "filmes lucrativos" if profit else "filmes com nota 8 ou mais"
            observations = [
                f"A cobertura passou de {n0} de {before['total_filmes']} lançamentos em {start} "
                f"para {n1} de {after['total_filmes']} em {end}. Entre os filmes com dados, "
                f"a proporção de {detail} passou de {share0}% para {share1}%.",
            ]
            if profit:
                average0, average1 = a / n0, b / n1
                volume = (n1 - n0) * average0
                average = n1 * (average1 - average0)
                answer += (
                    " O número de filmes com receita e orçamento registrados "
                    f"passou de {n0} para {n1}, e o lucro médio por filme passou de "
                    f"{format_result_value('lucro_brl', average0)} "
                    f"para {format_result_value('lucro_brl', average1)}."
                )
                observations.append(
                    f"Na decomposição do lucro total, a mudança no número de filmes com dados "
                    f"contribuiu com {format_result_value('lucro_brl', volume)} usando a média "
                    f"original. A mudança no lucro médio contribuiu com "
                    f"{format_result_value('lucro_brl', average)}."
                )
            else:
                answer += (
                    f" A parcela com nota 8 ou mais passou de {share0}% para {share1}% "
                    f"entre os filmes avaliados ({n0} em {start} e {n1} em {end})."
                )
            insights = tuple(observations)
    return AgentResponse(
        answer=answer, rows=result.rows, columns=result.columns,
        truncated=result.truncated, tool_calls=1, metric=label, period=f"{start} e {end}",
        unit="BRL" if profit else "pontos",
        limitations="a comparação descreve os filmes registrados e não identifica causas externas",
        insights=insights,
    )
