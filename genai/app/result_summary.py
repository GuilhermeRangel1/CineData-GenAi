"""Escreve uma resposta curta usando apenas o resultado da consulta."""

import re
from typing import Any

_LABELS = {
    "ano": "ano",
    "ano_lancamento": "ano",
    "nota_imdb": "nota no IMDb",
    "nota_media_imdb": "nota média no IMDb",
    "media_imdb": "nota média no IMDb",
    "media_nota_imdb": "nota média no IMDb",
    "qtd_imdb": "votos no IMDb",
    "qtd_avaliacoes_usuarios": "avaliações dos usuários",
    "filmes_avaliados": "filmes avaliados",
    "filmes_elegiveis": "filmes na conta",
    "filmes_lucrativos": "filmes que deram lucro",
    "qtd_lucraram": "filmes que deram lucro",
    "total_filmes": "total de filmes",
    "percentual_lucrativo": "percentual de filmes lucrativos",
    "percentual_informado": "percentual com ambos os valores informados",
    "percentual_bilheteria": "participação na bilheteria",
    "receita_por_real": "bilheteria por real de orçamento",
    "aumento_brl": "aumento da bilheteria",
    "margem": "margem",
    "margem_media": "margem média",
}
_ENTITIES = ("titulo", "nome_genero", "nome_produtora", "diretor", "nome_pessoa")
_ID_COLUMN = re.compile(r"^(?:id|id_.*|.*_id)$", re.IGNORECASE)
_GENRES = {
    "action": "Ação", "adventure": "Aventura", "animation": "Animação",
    "comedy": "Comédia", "crime": "Crime", "documentary": "Documentário",
    "drama": "Drama", "family": "Família", "fantasy": "Fantasia", "history": "História",
    "horror": "Terror", "music": "Música", "mystery": "Mistério", "romance": "Romance",
    "science fiction": "Ficção científica", "thriller": "Suspense", "tv movie": "Filme para TV",
    "war": "Guerra", "western": "Faroeste",
}


def genre_label(value: str) -> str:
    return _GENRES.get(value.strip().casefold(), value)


def format_result_value(column: str, value: str | int | float) -> str:
    if isinstance(value, str):
        if column in {"nome_genero", "genero"}:
            return genre_label(value)
        return " ".join(value.split())
    if column in {"ano", "ano_lancamento"}:
        return str(value)
    if column in {"margem", "margem_media"}:
        return format_result_value("percentual_margem", value * 100)
    is_currency = column.endswith("_brl")
    number = f"{value:,.2f}" if is_currency or isinstance(value, float) else f"{value:,}"
    number = number.translate(str.maketrans(",.", ".,"))
    if not is_currency and isinstance(value, float):
        number = number.rstrip("0").removesuffix(",")
    if is_currency:
        return f"R$ {number}"
    if column.startswith(("percentual_", "porcentagem_")):
        return f"{number}%"
    return number


def summarize_result(rows: tuple[dict[str, Any], ...]) -> str | None:
    """Resume a linha única ou cita os primeiros itens na ordem da consulta."""
    if not rows:
        return None
    first = rows[0]
    entity_column = next(
        (column for column in _ENTITIES if isinstance(first.get(column), str)), None
    )
    if len(rows) == 2 and entity_column is None:
        year_column = "ano_lancamento" if "ano_lancamento" in first else "ano"
        annual_metrics = {
            "lucro_brl": ("lucro total", "lucro_brl"),
            "lucro_total": ("lucro total", "lucro_brl"),
            "lucro_total_brl": ("lucro total", "lucro_brl"),
            "nota_media_imdb": ("nota média no IMDb", "nota_media_imdb"),
            "media_imdb": ("nota média no IMDb", "nota_media_imdb"),
        }
        if all(type(row.get(year_column)) is int for row in rows):
            for column, (label, display_column) in annual_metrics.items():
                if all(type(row.get(column)) in (int, float) for row in rows):
                    before, after = sorted(rows, key=lambda row: row[year_column])
                    if before[year_column] == after[year_column]:
                        break
                    return (
                        f"Em {before[year_column]}, {label}: "
                        f"{format_result_value(display_column, before[column])}. "
                        f"Em {after[year_column]}: "
                        f"{format_result_value(display_column, after[column])}."
                    )
    if len(rows) > 1:
        if entity_column is None:
            return None
        names = [
            format_result_value(entity_column, name)
            for row in rows[:3]
            if isinstance(name := row.get(entity_column), str) and name.strip()
        ]
        if not names:
            return None
        items = ", ".join(names[:-1]) + f" e {names[-1]}" if len(names) > 1 else names[0]
        prefix = "Encontrei" if len(names) == len(rows) else "A lista começa com"
        return f"{prefix} {items}."

    details = []
    for column, value in first.items():
        if (
            column == entity_column or _ID_COLUMN.match(column)
            or not isinstance(value, (str, int, float))
        ):
            continue
        label = _LABELS.get(column, column.removesuffix("_brl").replace("_", " "))
        details.append(f"{label}: {format_result_value(column, value)}")
    sentence = ", ".join(details[:3])
    if sentence:
        sentence = f"{sentence[0].upper()}{sentence[1:]}."
    if entity_column:
        name = format_result_value(entity_column, first[entity_column])
        return f"Encontrei {name}. {sentence}".rstrip()
    return sentence or None
