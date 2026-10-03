"""Validação de SQL SQLite antes da execução no Gold."""

import unicodedata
from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.errors import SqlValidationError
from app.gold_database import EXPECTED_TABLES

_GOLD_COLUMNS = frozenset(
    {
        "sk_movie_id",
        "id_filme",
        "titulo",
        "data_lancamento",
        "ano_lancamento",
        "duracao_minutos",
        "idioma_original",
        "status_filme",
        "sinopse",
        "url_poster",
        "url_backdrop",
        "orcamento_usd",
        "receita_usd",
        "lucro_usd",
        "orcamento_brl",
        "receita_brl",
        "lucro_brl",
        "popularidade",
        "nota_tmdb",
        "qtd_tmdb",
        "nota_imdb",
        "qtd_imdb",
        "sk_genre_id",
        "nome_genero",
        "sk_person_id",
        "nome_pessoa",
        "tipo_pessoa",
        "sk_company_id",
        "nome_produtora",
        "sk_review_id",
        "qtd_avaliacoes_usuarios",
        "nota_media_usuarios",
        "id",
        "sk_movie_review_id",
        "name",
        "rating",
        "text",
        "created_at",
    }
)

_MAX_SQL_LENGTH = 16_000
_MAX_CTES = 8
_MAX_JOINS = 8
_MAX_SUBQUERIES = 12
_DENIED_FUNCTIONS = frozenset({"load_extension", "readfile", "writefile", "randomblob", "zeroblob"})


def _without_accents(value: str) -> str:
    """Retorna um identificador ASCII para tolerar acentos introduzidos pelo modelo."""

    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(character)
    )


def _normalize_gold_columns(expression: exp.Expression) -> None:
    """Corrige apenas acentos em nomes de colunas Gold, sem tocar em literais."""

    for column in expression.find_all(exp.Column):
        normalized = _without_accents(column.name)
        if normalized in _GOLD_COLUMNS and normalized != column.name:
            column.set("this", exp.Identifier(this=normalized, quoted=False))


@dataclass(frozen=True)
class ValidatedQuery:
    """Consulta normalizada e pronta para o executor controlado."""

    sql: str
    tables: frozenset[str]


def validate_sql(sql: str, max_rows: int = 100) -> ValidatedQuery:
    """Aceita uma única consulta SELECT sobre as tabelas Gold permitidas."""

    if not sql or not sql.strip():
        raise SqlValidationError("A consulta SQL está vazia.")
    if max_rows < 1:
        raise ValueError("max_rows deve ser positivo.")
    if len(sql) > _MAX_SQL_LENGTH:
        raise SqlValidationError("A consulta SQL excede o tamanho permitido.")

    try:
        statements = parse(sql, read="sqlite")
    except ParseError as exc:
        raise SqlValidationError("A consulta SQL é inválida.") from exc

    if len(statements) != 1 or statements[0] is None:
        raise SqlValidationError("Apenas uma consulta SQL é permitida.")

    expression = statements[0]
    if not isinstance(expression, (exp.Select, exp.Union)):
        raise SqlValidationError("Somente consultas SELECT são permitidas.")

    _normalize_gold_columns(expression)

    ctes = tuple(expression.find_all(exp.CTE))
    if len(ctes) > _MAX_CTES:
        raise SqlValidationError("A consulta usa CTEs demais.")
    if any(with_clause.args.get("recursive") for with_clause in expression.find_all(exp.With)):
        raise SqlValidationError("CTEs recursivas não são permitidas.")
    if len(tuple(expression.find_all(exp.Join))) > _MAX_JOINS:
        raise SqlValidationError("A consulta usa joins demais.")
    if len(tuple(expression.find_all(exp.Subquery))) > _MAX_SUBQUERIES:
        raise SqlValidationError("A consulta usa subconsultas demais.")
    for join in expression.find_all(exp.Join):
        if join.args.get("kind") == "CROSS":
            raise SqlValidationError("CROSS JOIN não é permitido.")
    for function in expression.find_all(exp.Func):
        function_name = (function.name or function.sql_name()).casefold()
        if function_name in _DENIED_FUNCTIONS:
            raise SqlValidationError("A consulta usa uma função não permitida.")

    cte_names = {cte.alias_or_name for cte in expression.find_all(exp.CTE)}
    tables: set[str] = set()
    for table in expression.find_all(exp.Table):
        if table.name in cte_names:
            continue
        if table.db and table.db != "main":
            raise SqlValidationError("A consulta não pode acessar outro banco.")
        if table.name not in EXPECTED_TABLES:
            raise SqlValidationError("A consulta usa uma tabela não permitida.")
        tables.add(table.name)

    if not tables:
        raise SqlValidationError("A consulta precisa ler uma tabela Gold.")

    limits = tuple(expression.find_all(exp.Limit))
    if not limits:
        expression = expression.limit(max_rows)
    else:
        for limit in limits:
            limit_expression = limit.args.get("expression")
            if (
                isinstance(limit_expression, exp.Literal)
                and limit_expression.is_int
                and int(limit_expression.this) > max_rows
            ):
                limit.set("expression", exp.Literal.number(max_rows))

    return ValidatedQuery(sql=expression.sql(dialect="sqlite"), tables=frozenset(tables))
