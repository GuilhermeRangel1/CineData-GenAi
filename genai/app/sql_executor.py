"""Execução limitada de consultas SQL já validadas."""

import sqlite3
import time
from dataclasses import dataclass
from typing import Any

from app.errors import QueryExecutionError, QueryTimeoutError
from app.gold_database import EXPECTED_TABLES, GoldDatabase
from app.sql_guard import ValidatedQuery

_DENIED_ACTIONS = {
    sqlite3.SQLITE_ATTACH,
    sqlite3.SQLITE_DETACH,
    sqlite3.SQLITE_DELETE,
    sqlite3.SQLITE_DROP_INDEX,
    sqlite3.SQLITE_DROP_TABLE,
    sqlite3.SQLITE_DROP_TRIGGER,
    sqlite3.SQLITE_DROP_VIEW,
    sqlite3.SQLITE_INSERT,
    sqlite3.SQLITE_PRAGMA,
    sqlite3.SQLITE_TRANSACTION,
    sqlite3.SQLITE_UPDATE,
}


@dataclass(frozen=True)
class QueryResult:
    """Resultado tabular limitado para a camada da API."""

    columns: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]
    truncated: bool


class GoldQueryExecutor:
    """Executa apenas consultas previamente aprovadas pelo guard."""

    def __init__(
        self,
        database: GoldDatabase,
        max_rows: int = 100,
        timeout_seconds: float = 5.0,
        complex_timeout_seconds: float | None = None,
        pair_query_timeout_seconds: float | None = None,
        progress_steps: int = 100_000,
    ):
        self.database = database
        self.max_rows = max_rows
        self.timeout_seconds = timeout_seconds
        self.complex_timeout_seconds = complex_timeout_seconds or timeout_seconds
        self.pair_query_timeout_seconds = (
            pair_query_timeout_seconds or self.complex_timeout_seconds
        )
        self.progress_steps = progress_steps

    def execute(self, query: ValidatedQuery) -> QueryResult:
        """Executa uma consulta com autorização SQLite e limites operacionais."""

        with self.database.connect() as connection:
            if self._is_actor_director_pair_query(query.sql):
                # This aggregation creates a large GROUP BY work table. Keep its
                # temporary B-tree in memory instead of repeatedly writing it to disk.
                connection.execute("PRAGMA temp_store = MEMORY")
            connection.set_authorizer(self._authorize)
            deadline = time.monotonic() + self._timeout_for(query)
            connection.set_progress_handler(
                lambda: int(time.monotonic() >= deadline), self.progress_steps
            )
            try:
                cursor = connection.execute(query.sql)
                values = cursor.fetchmany(self.max_rows + 1)
            except sqlite3.OperationalError as exc:
                if "interrupted" in str(exc).lower():
                    raise QueryTimeoutError("A consulta excedeu o tempo máximo.") from exc
                raise QueryExecutionError("A consulta não pôde ser executada.") from exc
            except sqlite3.Error as exc:
                raise QueryExecutionError("A consulta não pôde ser executada.") from exc
            finally:
                connection.set_progress_handler(None, 0)

        columns = tuple(description[0] for description in cursor.description or ())
        truncated = len(values) > self.max_rows
        rows = tuple(dict(zip(columns, row, strict=True)) for row in values[: self.max_rows])
        return QueryResult(columns=columns, rows=rows, truncated=truncated)

    def _timeout_for(self, query: ValidatedQuery) -> float:
        """Reserva mais tempo para varreduras e agregações no Gold."""

        sql = query.sql.upper()
        if self._is_actor_director_pair_query(sql):
            return max(self.timeout_seconds, self.pair_query_timeout_seconds)

        is_expensive_gold_query = any(
            table in sql
            for table in ("BRIDGE_MOVIE_", "DIM_REVIEWS", "FACT_MOVIES_PERFORMANCE")
        )
        if is_expensive_gold_query:
            return max(self.timeout_seconds, self.complex_timeout_seconds)
        return self.timeout_seconds

    @staticmethod
    def _is_actor_director_pair_query(sql: str) -> bool:
        """Identifies the bounded mandatory co-credit aggregate."""

        normalized = sql.upper()
        return (
            "ACTOR_LINKS AS MATERIALIZED" in normalized
            and "DIRECTOR_LINKS AS MATERIALIZED" in normalized
            and "PAIR_COUNTS AS MATERIALIZED" in normalized
        )

    def _authorize(self, action: int, arg1: str | None, arg2: str | None, *_args: Any) -> int:
        if action in _DENIED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1 not in EXPECTED_TABLES:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and arg2 in {
            "load_extension",
            "readfile",
            "writefile",
        }:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK
