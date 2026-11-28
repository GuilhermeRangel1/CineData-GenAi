import sqlite3

from app.analytical_insights import analytical_insights
from app.revenue_investigation import finance_coverage_context
from app.sql_executor import QueryResult


def test_vote_cutoff_explains_why_titles_left_the_ranking() -> None:
    rows = (
        {"titulo": "A", "nota_imdb": 9, "qtd_imdb": 9_999},
        {"titulo": "B", "nota_imdb": 8.9, "qtd_imdb": 10_000},
    )
    insight, = analytical_insights(
        rows,
        question="quem sai do top 10 por nota imdb se o minimo de votos subir de mil pra 10 mil?",
    )
    assert "1 dos 2 títulos" in insight
    assert "menos de 10.000 votos" in insight


def test_financial_coverage_changes_on_the_first_day_of_the_year() -> None:
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript("""
        CREATE TABLE dim_movies (sk_movie_id INTEGER, data_lancamento TEXT);
        CREATE TABLE dim_genres (sk_genre_id INTEGER, nome_genero TEXT);
        CREATE TABLE bridge_movie_genre (sk_movie_id INTEGER, sk_genre_id INTEGER);
        CREATE TABLE fact_movies_performance
            (sk_movie_id INTEGER, receita_brl REAL, orcamento_brl REAL);
        INSERT INTO dim_genres VALUES (1, 'Animation');
        INSERT INTO dim_movies VALUES
            (1,'2024-12-31'), (2,'2025-01-01'), (3,'2026-01-01');
        INSERT INTO bridge_movie_genre VALUES (1,1), (2,1), (3,1);
        INSERT INTO fact_movies_performance VALUES (1,5,6), (2,8,8), (3,NULL,10);
    """)

    class FixedDateExecutor:
        def __init__(self, today: str) -> None:
            self.today = today

        def execute(self, query) -> QueryResult:
            cursor = db.execute(query.sql.replace("'now'", f"'{self.today}'"))
            return QueryResult(
                tuple(column[0] for column in cursor.description),
                tuple(dict(row) for row in cursor),
                False,
            )

    question = "que animacoes do ano anterior recuperaram pelo menos o orcamento?"
    previous = finance_coverage_context(question, FixedDateExecutor("2025-12-31"), 100)
    next_year = finance_coverage_context(question, FixedDateExecutor("2026-01-01"), 100)
    assert any("Nenhum desses recuperou o orçamento." in item for item in previous)
    assert next_year == ()
