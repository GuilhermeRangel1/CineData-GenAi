from datetime import date

import pytest
from pydantic import ValidationError

from app.movies.schemas import AvaliacaoCriacao, ConsultaCatalogo, FilmeAtualizacao, FilmeCriacao


def test_movie_creation_contract_accepts_required_fields() -> None:
    filme = FilmeCriacao(
        titulo="A Viagem de Chihiro",
        diretor="Hayao Miyazaki",
        ano_lancamento=2001,
        generos=["Animação", "Fantasia"],
        sinopse="Uma jovem atravessa um mundo fantástico.",
    )

    assert filme.titulo == "A Viagem de Chihiro"
    assert filme.generos == ["Animação", "Fantasia"]


def test_review_contract_accepts_rating_on_zero_to_ten_scale() -> None:
    avaliacao = AvaliacaoCriacao(nota=10, comentario="Ótimo filme.")

    assert avaliacao.nota == 10


def test_review_contract_rejects_rating_outside_zero_to_ten_scale() -> None:
    with pytest.raises(ValidationError):
        AvaliacaoCriacao(nota=10.1, comentario="Ótimo filme.")


def test_review_contract_defaults_to_public_visibility_and_rejects_invalid_values() -> None:
    assert AvaliacaoCriacao(nota=8, comentario="Ótimo filme.").visibilidade == "publica"
    with pytest.raises(ValidationError):
        AvaliacaoCriacao(nota=8, comentario="Ótimo filme.", visibilidade="amigos")


def test_catalog_query_contract_defines_stable_default_order() -> None:
    consulta = ConsultaCatalogo()

    assert consulta.ordenar_por == "relevancia"
    assert consulta.direcao == "asc"


def test_catalog_query_contract_rejects_an_inverted_year_range() -> None:
    with pytest.raises(ValidationError):
        ConsultaCatalogo(ano_inicial=2025, ano_final=2020)


def test_catalog_query_contract_ignores_empty_and_nullish_optional_filters() -> None:
    consulta = ConsultaCatalogo(pessoa="  ", duracao_minima="null", nota_minima="undefined")

    assert consulta.pessoa is None
    assert consulta.duracao_minima is None
    assert consulta.nota_minima is None


def test_catalog_query_contract_rejects_an_inverted_duration_range() -> None:
    with pytest.raises(ValidationError):
        ConsultaCatalogo(duracao_minima=180, duracao_maxima=90)


def test_movie_creation_contract_rejects_year_that_differs_from_release_date() -> None:
    with pytest.raises(ValidationError):
        FilmeCriacao(
            titulo="Filme inconsistente",
            diretor="Diretora",
            ano_lancamento=2023,
            data_lancamento=date(2024, 1, 1),
            generos=["Drama"],
        )


def test_movie_update_contract_rejects_empty_payload_and_null_required_relations() -> None:
    with pytest.raises(ValidationError):
        FilmeAtualizacao()
    with pytest.raises(ValidationError):
        FilmeAtualizacao(diretor=None)


def test_movie_contract_accepts_only_a_safe_youtube_trailer_url() -> None:
    filme = FilmeCriacao(
        titulo="Filme com trailer",
        diretor="Diretora",
        generos=["Drama"],
        url_trailer="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    )

    assert filme.url_trailer == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    with pytest.raises(ValidationError):
        FilmeCriacao(
            titulo="Origem inválida",
            diretor="Diretora",
            generos=["Drama"],
            url_trailer="https://example.com/trailer",
        )
