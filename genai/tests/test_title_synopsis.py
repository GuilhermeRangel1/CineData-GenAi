import sqlite3
from unittest.mock import Mock

import httpx
import pytest

from app.agent_models import ConversationContext, ModelTurn
from app.gold_database import GoldDatabase
from app.title_synopsis import _detail_request, _request, answer_title_synopsis


def test_synopsis_request_keeps_a_compound_spoiler_instruction_out_of_the_title():
    question = "Pode me contar a história de O Menu, só a premissa e sem revelar o final?"
    assert _request(question) == ("O Menu", None)


def test_synopsis_request_keeps_character_outcome_out_of_the_title():
    question = "Me conta a premissa de O Homem do Norte, sem revelar quem sobrevive."
    assert _request(question) == ("O Homem do Norte", None)


@pytest.mark.parametrize(("question", "metrics", "title"), [
    ("Quem dirigiu Barbie e quanto ela arrecadou?",
     ("quem dirigiu", "quanto arrecadou"), ("Barbie", None)),
    ("Quanto custou Duna (2021) e quem dirigiu?",
     ("orçamento", "quem dirigiu"), ("Duna", 2021)),
    ("Quem dirigiu, quanto custou e que nota tem Oppenheimer?",
     ("quem dirigiu", "orçamento", "nota"), ("Oppenheimer", None)),
    ("Quanto tempo dura e em que ano estreou Barbie?",
     ("duração", "estreia"), ("Barbie", None)),
    ("E a nota?", ("nota",), None),
    ("E quanto tempo dura ele?", ("duração",), None),
    ("E qual é a duração dele?", ("duração",), None),
    ("Qual o orçamento desse filme?", ("orçamento",), None),
    ("E a nota desse filme?", ("nota",), None),
    ("Quanto tempo ele dura?", ("duração",), None),
    ("Quem foi que dirigiu mesmo?", ("quem dirigiu",), None),
    ("E quem tá no elenco?", ("quem atuou",), None),
    ("E quanto arrecadou o último filme que você achou?", ("quanto arrecadou",), None),
    ("E quem dirigiu Logan mesmo?", ("quem dirigiu",), ("Logan", None)),
    ("Quanto tempo dura Zotopia, aquela da coelha policial?", ("duração",), ("Zotopia", None)),
    ("Quanto tempo dura Elementl, aquela dos elementos?", ("duração",), ("Elementl", None)),
    ("Qual foi a nota de A Forma da Água no TMDB?", ("nota tmdb",), ("A Forma da Água", None)),
    ("Me passa a duração de Top Gun: Maverick.", ("duração",), ("Top Gun: Maverick", None)),
    ("Quem dirigiu Ford vs Ferrari e que nota ele tem no IMDb?",
     ("quem dirigiu", "nota imdb"), ("Ford vs Ferrari", None)),
])
def test_movie_details_extract_one_title_for_all_metrics(question, metrics, title):
    assert _detail_request(question) == (metrics, title)


@pytest.mark.parametrize("question", [
    "Qual é o lucro médio em BRL por gênero?",
    "Qual foi o orçamento mediano dos filmes de terror de 2024?",
    "Quem dirigiu mais filmes?",
    "Quem dirigiu Barbie e qual foi o orçamento de Oppenheimer?",
])
def test_movie_details_leave_other_intents_to_analytical_agent(question):
    assert _detail_request(question) is None


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
    duration_question = "Quanto tempo dura O Farol?"
    assert "2015, 2020" in ask(duration_question).answer
    previous = (
        ConversationContext(question="Quanto tempo dura O Farol (2020)?"),
        ConversationContext(question="Quanto tempo dura Filme Inexistente?"),
    )
    assert "100 minutos" in ask("E quanto tempo dura esse aí?", previous).answer
    duration = ask("De 2020", (ConversationContext(question=duration_question),))
    assert duration.answer == "O Farol (2020)\n\nDuração: 100 minutos."
    model.complete.assert_not_called()

    response = ask("De 2020", (ConversationContext(question=question),))
    assert response.answer == f"O Farol (2020)\n\n{portuguese}"
    assert original in model.complete.call_args.args[0][1]["content"]
    assert model.complete.call_args.args[1] == ()

    model.complete.reset_mock()
    model.complete.side_effect = [
        ModelTurn(answer="A detetive investiga o caso relying-se nas pistas do porto."),
        ModelTurn(answer=portuguese),
    ]
    assert portuguese in ask("Qual a sinopse de O Farol de 2020, sem spoilers?").answer
    assert model.complete.call_count == 2

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
