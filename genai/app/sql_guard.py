"""Validação de SQL SQLite antes da execução no Gold."""

from dataclasses import dataclass

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from app.errors import SqlValidationError
from app.gold_database import EXPECTED_TABLES


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

    try:
        statements = parse(sql, read="sqlite")
    except ParseError as exc:
        raise SqlValidationError("A consulta SQL é inválida.") from exc

    if len(statements) != 1 or statements[0] is None:
        raise SqlValidationError("Apenas uma consulta SQL é permitida.")

    expression = statements[0]
    if not isinstance(expression, (exp.Select, exp.Union)):
        raise SqlValidationError("Somente consultas SELECT são permitidas.")

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

    limit = expression.args.get("limit")
    if limit is None:
        expression = expression.limit(max_rows)
    else:
        limit_expression = limit.args.get("expression")
        if (
            isinstance(limit_expression, exp.Literal)
            and limit_expression.is_int
            and int(limit_expression.this) > max_rows
        ):
            limit.set("expression", exp.Literal.number(max_rows))

    return ValidatedQuery(sql=expression.sql(dialect="sqlite"), tables=frozenset(tables))
