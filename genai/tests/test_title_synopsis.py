import sqlite3
from unittest.mock import Mock

import httpx

from app.agent_models import ConversationContext, ModelTurn
from app.gold_database import GoldDatabase
from app.title_synopsis import answer_title_synopsis


def test_catalog_synopsis_lookup_and_translation(tmp_path):
    path = tmp_path / "gold.db"
    original = "A young detective investigates a disappearance in a small coastal town."
    portuguese = "Uma jovem detetive investiga um desaparecimento em uma cidade costeira."
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE dim_movies (sk_movie_id, titulo, ano_lancamento, sinopse)")
        connection.execute("ALTER TABLE dim_movies ADD COLUMN id_filme TEXT")
        connection.execute("ALTER TABLE dim_movies ADD COLUMN duracao_minutos INTEGER")
        connection.executemany(
            "INSERT INTO dim_movies (sk_movie_id, titulo, ano_lancamento, sinopse) "
            "VALUES (?, ?, ?, ?)",
            [
                (1, "O Farol", 2015, portuguese),
                (2, "O Farol", 2020, original),
                (3, "O Farol", 2020, "Sem descrição"),
                (4, "O Castelo", 2020, "Sem descrição"),
            ],
        )
        connection.execute("UPDATE dim_movies SET duracao_minutos = 100 WHERE sk_movie_id = 2")
        connection.execute("UPDATE dim_movies SET duracao_minutos = 10 WHERE sk_movie_id = 3")
    model = Mock()
    model.complete.return_value = ModelTurn(answer=portuguese)
    database = GoldDatabase(path)

    def ask(question, previous=()):
        return answer_title_synopsis(question, previous, database, model, True)

    question = "Sobre o que fala O Farol?"
    assert "2015, 2020" in ask(question).answer
    assert portuguese in ask("Me conta a historia de O Farol (2015)?").answer
    assert "não tem sinopse" in ask("Qual é a sinopse do filme O Castelo?").answer
    assert "Não encontrei" in ask("Do que trata Filme Inexistente?").answer
    assert ask("Quais filmes falam sobre detetives?") is None
    model.complete.assert_not_called()

    response = ask("De 2020", (ConversationContext(question=question),))
    assert response.answer == f"O Farol (2020)\n\n{portuguese}"
    assert original in model.complete.call_args.args[0][1]["content"]
    assert model.complete.call_args.args[1] == ()

    model.complete.side_effect = TimeoutError
    fallback = ask("Qual a sinopse de O Farol de 2020?").answer
    assert "A versão em português está indisponível" in fallback
    assert original in fallback


def test_brazilian_title_links_to_catalog_by_tmdb_id(tmp_path, monkeypatch):
    path = tmp_path / "gold.db"
    synopsis = "Um jovem leão precisa recuperar o reino depois de fugir de sua terra natal."
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE dim_movies "
            "(sk_movie_id, id_filme, titulo, ano_lancamento, sinopse, duracao_minutos)"
        )
        connection.execute(
            "INSERT INTO dim_movies VALUES (1, '420818', 'The Lion King', 2019, ?, 118)",
            (synopsis,),
        )
    monkeypatch.setattr("app.title_synopsis.httpx.get", lambda *args, **kwargs: httpx.Response(
        200,
        request=httpx.Request("GET", "https://api.themoviedb.org/3/search/movie"),
        json={"results": [
            {"id": 420818, "title": "O Rei Leão", "original_title": "The Lion King"},
            {"id": 8587, "title": "O Rei Leão", "original_title": "The Lion King"},
        ]},
    ))
    model = Mock()
    for title in ("O Rei Leao", "The Lion King"):
        result = answer_title_synopsis(
            f"Sobre o que fala {title}?", (), GoldDatabase(path), model, False,
            tmdb_token="test-token",
        )
        assert result.answer == f"O Rei Leão (2019)\n\n{synopsis}"
    model.complete.assert_not_called()
