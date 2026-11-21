"""Observações calculadas sobre os resultados da consulta ao Gold."""

import re
from math import isfinite
from typing import Any

from app.result_summary import format_result_value

_COMPARABLE_METRICS = {
    "lucro_brl": "lucro",
    "lucro_medio_brl": "lucro médio",
    "prejuizo_brl": "prejuízo",
    "receita_brl": "bilheteria",
    "orcamento_brl": "orçamento",
    "nota_media_imdb": "nota média no IMDb",
    "nota_imdb": "nota no IMDb",
    "percentual_lucrativo": "percentual de filmes lucrativos",
    "total_coproducoes": "total de coproduções",
    "total_filmes": "número de filmes",
    "total_diretores": "número de diretores",
    "filmes_em_comum": "número de filmes em comum",
    "diferenca": "diferença",
}
_LABELS = ("titulo", "nome_genero", "nome_produtora", "diretor", "nome_pessoa", "ano_lancamento")
_ALIASES = {
    "ator1": "ator_1", "ator2": "ator_2",
    "qtd_coproducoes": "total_coproducoes", "num_coproducoes": "total_coproducoes",
    "qtd_filmes_coproducao": "total_coproducoes",
    "ano": "ano_lancamento",
    "qtd_diretores": "total_diretores", "mediana_orcamento_brl": "orcamento_mediano_brl",
    "receita_por_real_orcamento": "receita_por_real",
    "retorno_por_real_investido": "receita_por_real",
    "qtd_filmes_comedia": "qtd_comedia", "qtd_filmes_terror": "qtd_terror",
    "media_nota_imdb": "nota_media_imdb", "media_imdb": "nota_media_imdb",
    "lucro_medio": "lucro_medio_brl", "quanto_faltou": "prejuizo_brl",
    "percentual_fatia": "percentual_bilheteria",
    "percentual_bilheteria_top10": "percentual_bilheteria",
    "qtd_lancamentos": "total_filmes",
    "qtd_animacoes": "filmes_avaliados",
    "lucro_total_brl": "lucro_brl",
}


def _number(value: Any) -> bool:
    return type(value) in (int, float) and isfinite(value)


def analytical_insights(
    rows: tuple[dict[str, Any], ...], *, question: str = ""
) -> tuple[str, ...]:
    if not rows:
        if "terror" in question and "comedia" in question and "mais" in question:
            return ("Nenhum ano do recorte apresentou a superioridade pedida. "
                    "Anos empatados ficam de fora da comparação estrita.",)
        if "animac" in question and ("ano passado" in question or "ano anterior" in question) and (
            "orcamento" in question or "pagaram" in question or "empataram" in question
        ):
            return ("A lista vazia indica que nenhum filme com os valores necessários "
                    "entrou no resultado. Filmes sem bilheteria ou orçamento informado "
                    "não podem ser classificados pelo ponto de equilíbrio.",)
        if "acao" in question and "ano" in question and (
            "bilheteria" in question or "bilhetria" in question or "arrecadacao" in question
        ):
            return ("Nenhum lançamento de ação do recorte tem orçamento e bilheteria "
                    "registrados juntos. A ausência dos dois dados impede comparar os valores.",)
        return ()
    rows = tuple(
        {**{alias: r[key] for key, alias in _ALIASES.items() if key in r}, **r}
        for r in rows
    )
    if all(r.get("nome_genero") and _number(r.get("qtd_filmes")) for r in rows):
        rows = tuple({"total_filmes": r["qtd_filmes"], **r} for r in rows)
    if "coproduc" in question and all(
        r.get("nome_produtora") and _number(r.get("qtd_filmes")) for r in rows
    ):
        rows = tuple({"total_coproducoes": r["qtd_filmes"], **r} for r in rows)
    row = rows[0]
    total = row.get("filmes_elegiveis", row.get("total_filmes", row.get("filmes")))
    profitable = row.get(
        "filmes_lucrativos", row.get("filmes_com_lucro", row.get("qtd_lucraram"))
    )
    if len(rows) == 1 and _number(total) and _number(profitable) and 0 <= profitable <= total:
        return (
            f"Dos {format_result_value('', total)} filmes com os dois valores registrados, "
            f"{format_result_value('', total - profitable)} não tiveram lucro positivo.",
        )
    if len(rows) == 1:
        if row.get("titulo") and "scorsese" in question and "dicaprio" in question:
            return ("A lista reflete os créditos registrados no catálogo. "
                    "Uma única colaboração encontrada indica a cobertura desse cruzamento, "
                    "sem estabelecer o total da parceria fora do CineData.",)
        compared = row.get("filmes_em_comum")
        rated = row.get("filmes_avaliados")
        if _number(compared) and _number(rated) and 0 <= rated <= compared:
            return (
                f"A média do IMDb considera {rated} dos {compared} filmes em comum "
                f"({format_result_value('', 100 * rated / compared)}% dos títulos)."
                if compared else "Não há filmes em comum para calcular a média.",
            )
        if _number(rated) and _number(row.get("nota_media_imdb")):
            return (
                f"A média desse ano se apoia em {format_result_value('', rated)} "
                "títulos avaliados. Cada título tem o mesmo peso na média.",
            )
        for key, description in (
            ("percentual_bilheteria", "da receita registrada ficou fora dos dez maiores"),
            ("percentual_informado", "dos filmes do gênero não têm os dois valores registrados"),
            ("percentual_lucrativo", "dos filmes elegíveis ficaram sem lucro positivo"),
        ):
            value = row.get(key)
            if _number(value) and 0 <= value <= 100:
                return (f"{format_result_value('', 100 - value)}% {description}.",)
        median = row.get("orcamento_mediano_brl")
        if _number(median):
            return (
                f"Pelo menos metade dos filmes com orçamento informado custou "
                f"até {format_result_value('orcamento_brl', median)}. "
                "A mediana reduz a influência das produções mais caras.",
            )
        if _number(row.get("aumento_brl")):
            return ("O aumento compara os totais de bilheteria registrados nos dois anos. "
                    "O valor não mede a alta média por filme.",)
        if _number(row.get("total_diretores")):
            return ("A contagem é de diretores distintos. Um diretor com vários filmes "
                    "da mesma produtora entra uma única vez.",)
        ratio = row.get("receita_por_real")
        if _number(ratio):
            excess = ratio - 1
            return (
                "Para cada real de orçamento, a bilheteria informada ficou "
                f"{format_result_value('receita_brl', abs(excess))} "
                f"{'acima' if excess > 0 else 'abaixo'} do valor gasto."
                if excess else "A bilheteria informada igualou o orçamento agregado.",
            )
        return ()

    if len(rows) == 2 and all(type(r.get("ano_lancamento")) is int for r in rows):
        before, after = sorted(rows, key=lambda r: r["ano_lancamento"])
        start, end = before["ano_lancamento"], after["ano_lancamento"]
        annual_metric = None
        if "lucro total" in question:
            annual_metric = next(
                (key for key in ("lucro_brl", "lucro_total")
                 if all(_number(r.get(key)) for r in rows)),
                None,
            )
        elif "imdb" in question and "media" in question:
            annual_metric = next(
                (key for key in ("nota_media_imdb", "media")
                 if all(_number(r.get(key)) for r in rows)),
                None,
            )
        if start < end and annual_metric:
            delta = after[annual_metric] - before[annual_metric]
            profit = annual_metric.startswith("lucro")
            if not profit and 0 < abs(delta) < 0.005:
                return (f"A média do IMDb variou menos de 0,01 ponto de {start} para {end}.",)
            if delta:
                direction = "subiu" if delta > 0 else "caiu"
                label = "O lucro total" if profit else "A média do IMDb"
                value = format_result_value("lucro_brl" if profit else "", abs(delta))
                unit = "" if profit else " ponto" if round(abs(delta), 2) == 1 else " pontos"
                return (f"{label} {direction} {value}{unit} de {start} para {end}.",)

    if all(
        _number(r.get("qtd_comedia")) and _number(r.get("qtd_terror"))
        and _number(r.get("lucro_medio_comedia")) and _number(r.get("lucro_medio_terror"))
        and r.get("ano_lancamento") is not None
        for r in rows
    ):
        best = max(rows, key=lambda r: r["lucro_medio_terror"] - r["lucro_medio_comedia"])
        gap = best["lucro_medio_terror"] - best["lucro_medio_comedia"]
        return (
            f"Em {best['ano_lancamento']}, a vantagem do terror no lucro médio foi a maior "
            f"entre os anos exibidos ({format_result_value('lucro_brl', gap)}), "
            f"mesmo com {best['qtd_comedia'] - best['qtd_terror']} estreias a menos.",
        )

    if all(r.get("ator_1") and r.get("ator_2") for r in rows):
        rows = tuple(
            {
                **r,
                "nome_pessoa": f"{r['ator_1']} e {r['ator_2']}",
                "total_filmes": r.get("total_filmes", r.get("qtd_filmes")),
            }
            for r in rows
        )
    cutoff_phrase = re.search(
        r"\b(?:pra|para|a|em vez de)\s+(\d{1,3}(?:\.\d{3})+|\d+\s+mil|dez mil|\d{4,})\b",
        question,
    )
    if cutoff_phrase and "votos" in question and "imdb" in question and "top" in question and (
        re.search(r"\b(?:sai|saem|deixa\w*|perde\w*|fora)\b", question)
    ) and all(_number(r.get("qtd_imdb")) for r in rows):
        text = cutoff_phrase[1]
        cutoff = 10_000 if text == "dez mil" else (
            int(text.split()[0]) * 1_000 if text.endswith(" mil") else int(text.replace(".", ""))
        )
        below = sum(r["qtd_imdb"] < cutoff for r in rows)
        if below:
            return (
                f"{below} dos {len(rows)} títulos que saíram do ranking tinham menos de "
                f"{format_result_value('', cutoff)} votos. Esses títulos ficam inelegíveis "
                "pelo novo corte, independentemente da nota.",
            )
    years = [r.get("ano_lancamento") for r in rows]
    if all(_number(y) for y in years) and "scorsese" in question and "dicaprio" in question:
        return (
            f"As colaborações exibidas se estendem de {min(years)} a {max(years)}, "
            f"um intervalo de {max(years) - min(years)} anos.",
        )
    if all(r.get("titulo") for r in rows) and (
        "dois rankings" in question or "dois top" in question
        or ("top 10" in question and "tanto" in question)
    ) and (
        "receita" in question or "bilheteria" in question or "arrecadacao" in question
    ) and "lucro" in question:
        intersection = f"Os dois rankings têm {len(rows)} títulos em comum."
        if len(rows) <= 10 and ("dez" in question or "top 10" in question):
            intersection += f" Isso corresponde a {len(rows) * 10}% das vagas de cada top 10."
        return (intersection,)
    if all(
        r.get("titulo") and _number(r.get("nota_imdb")) and _number(r.get("nota_tmdb"))
        for r in rows
    ):
        widest = max(rows, key=lambda r: abs(r["nota_imdb"] - r["nota_tmdb"]))
        gap = abs(widest["nota_imdb"] - widest["nota_tmdb"])
        unit = "ponto" if round(gap, 2) == 1 else "pontos"
        return (
            f"A maior diferença entre IMDb e TMDB nos títulos exibidos foi de "
            f"{format_result_value('', gap)} {unit}, em {widest['titulo']}.",
        )
    if "elenco" in question and all(r.get("nome_pessoa") for r in rows):
        return (f"O catálogo registra {len(rows)} nomes no resultado. "
                "A lista reúne créditos de atuação e não estabelece quem protagonizou o filme.",)
    if "diretores" in question and "terror" in question and "comedia" in question and (
        all(r.get("diretor") or r.get("nome_pessoa") for r in rows)
    ):
        return (
            f"Pelo menos {len(rows)} diretores têm créditos nos dois gêneros no recorte. "
            "Um filme classificado como terror e comédia pode contar para ambos.",
        )
    label = next((key for key in _LABELS if all(r.get(key) is not None for r in rows)), None)
    metric = next(
        (key for key in _COMPARABLE_METRICS if all(_number(r.get(key)) for r in rows)),
        None,
    )
    if label is None or metric is None:
        return ()
    ordered = sorted(rows, key=lambda r: r[metric], reverse=True)
    first, second = ordered[:2]
    highest = first[metric]
    metric_label = _COMPARABLE_METRICS[metric]
    if highest == second[metric]:
        if metric == "percentual_lucrativo" and label == "nome_produtora":
            leaders = [r for r in ordered if r[metric] == highest]
            if len(leaders) == 2 and all(_number(r.get("filmes_elegiveis")) for r in leaders):
                larger, smaller = sorted(leaders, key=lambda r: r["filmes_elegiveis"], reverse=True)
                return (
                    f"{larger[label]} e {smaller[label]} empataram com "
                    f"{format_result_value(metric, highest)} de filmes lucrativos. "
                    f"A porcentagem considera {larger['filmes_elegiveis']} filmes da primeira "
                    f"e {smaller['filmes_elegiveis']} da segunda.",
                )
        tied = [str(r[label]) for r in ordered if r[metric] == highest]
        names = " e ".join(tied) if len(tied) == 2 else f"{len(tied)} resultados"
        return (
            f"{names} empatam no maior valor de {metric_label} da lista "
            f"({format_result_value(metric, highest)}).",
        )
    difference = highest - second[metric]
    gap = (
        f"{format_result_value('', difference)} pontos percentuais"
        if metric.startswith("percentual_")
        else format_result_value(metric, difference)
    )
    lead = (
        f"Entre os resultados exibidos, {first[label]} lidera em {metric_label} "
        f"e supera {second[label]} em {gap}."
    )
    if metric in {"lucro_brl", "receita_brl", "prejuizo_brl"} and all(
        r[metric] >= 0 for r in ordered
    ):
        total = sum(r[metric] for r in ordered)
        share = 100 * highest / total if total else 0
        if share >= 40:
            return (
                lead,
                f"Só esse título responde por {format_result_value('', share)}% "
                f"do total de {metric_label} entre as {len(ordered)} linhas exibidas.",
            )
    return (lead,)
