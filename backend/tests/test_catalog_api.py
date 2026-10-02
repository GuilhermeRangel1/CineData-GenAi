from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from decimal import Decimal

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.db.session import get_db
from app.integrations.tmdb import TmdbGateway
from app.main import app
from app.movies.models import (
    DimCompany,
    DimGenre,
    DimMovie,
    DimPerson,
    DimReview,
    FactMoviePerformance,
    MovieReview,
)
from app.users.dependencies import get_current_admin, get_current_user
from app.users.models import User


CATALOG_SEARCH_TABLES = (
    ("dim_movies", "dim_movies_search", "titulo"),
    ("dim_people", "dim_people_search", "nome_pessoa"),
    ("dim_companies", "dim_companies_search", "nome_produtora"),
)


def _create_catalog_search_indexes(connection: Connection) -> None:
    """Reproduz os índices FTS criados pela migração 0021 nos bancos de teste."""

    for table_name, search_name, column_name in CATALOG_SEARCH_TABLES:
        connection.exec_driver_sql(
            f"""CREATE VIRTUAL TABLE {search_name} USING fts5(
                {column_name},
                content='{table_name}',
                content_rowid='rowid',
                tokenize='trigram',
                columnsize=0
            )"""
        )
        connection.exec_driver_sql(
            f"""CREATE TRIGGER {search_name}_ai AFTER INSERT ON {table_name} BEGIN
                INSERT INTO {search_name}(rowid, {column_name})
                VALUES (new.rowid, new.{column_name});
            END"""
        )
        connection.exec_driver_sql(
            f"""CREATE TRIGGER {search_name}_ad AFTER DELETE ON {table_name} BEGIN
                INSERT INTO {search_name}({search_name}, rowid, {column_name})
                VALUES ('delete', old.rowid, old.{column_name});
            END"""
        )
        connection.exec_driver_sql(
            f"""CREATE TRIGGER {search_name}_au AFTER UPDATE OF {column_name}
                ON {table_name} BEGIN
                INSERT INTO {search_name}({search_name}, rowid, {column_name})
                VALUES ('delete', old.rowid, old.{column_name});
                INSERT INTO {search_name}(rowid, {column_name})
                VALUES (new.rowid, new.{column_name});
            END"""
        )


@pytest.fixture(autouse=True)
def authenticated_actor_overrides() -> Iterator[None]:
    """Mantém os testes do catálogo focados no comportamento de cada rota."""

    async def standard_user() -> User:
        return User(id="user-1", email="ana@example.com", nome="Ana", password_hash="hash")

    async def administrator() -> User:
        return User(
            id="admin-1",
            email="admin@example.com",
            nome="Admin",
            password_hash="hash",
            role="admin",
        )

    app.dependency_overrides[get_current_user] = standard_user
    app.dependency_overrides[get_current_admin] = administrator
    try:
        yield
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
async def catalog_session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.run_sync(_create_catalog_search_indexes)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        drama = DimGenre(nome_genero="Drama")
        ficcao = DimGenre(nome_genero="Ficção científica")
        diretora = DimPerson(nome_pessoa="Denis Villeneuve", tipo_pessoa="Diretor")
        atriz = DimPerson(nome_pessoa="Amy Adams", tipo_pessoa="Ator")
        produtora = DimCompany(nome_produtora="Paramount Pictures")
        chegada = DimMovie(
            id_filme="movie-1",
            titulo="A Chegada",
            ano_lancamento=2016,
            duracao_minutos=116,
            status_filme="Lançado",
            url_trailer="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            genres=[ficcao, drama],
            people=[diretora, atriz],
            companies=[produtora],
            performance=FactMoviePerformance(
                orcamento_usd=Decimal("47000000"),
                receita_usd=Decimal("203388186"),
                lucro_usd=Decimal("156388186"),
                orcamento_brl=Decimal("147921000"),
                receita_brl=Decimal("640673785"),
                lucro_brl=Decimal("492752785"),
                popularidade=31.5,
                nota_tmdb=7.6,
                qtd_tmdb=17200,
                nota_imdb=7.9,
                qtd_imdb=780000,
            ),
            reviews_summary=DimReview(qtd_avaliacoes_usuarios=1, nota_media_usuarios=8.5),
            reviews=[
                MovieReview(
                    nome="Maria",
                    nota=8.5,
                    comentario="Ficção científica envolvente.",
                    # Distinguish history from new writes even within the same SQLite second.
                    created_at=datetime(2020, 1, 1),
                )
            ],
        )
        session.add_all(
            [
                User(
                    id="user-1",
                    email="ana@example.com",
                    nome="Ana",
                    password_hash="hash",
                ),
                User(
                    id="admin-1",
                    email="admin@example.com",
                    nome="Admin",
                    password_hash="hash",
                    role="admin",
                ),
                DimMovie(id_filme="movie-2", titulo="Zodíaco", ano_lancamento=2007, genres=[drama]),
                chegada,
            ]
        )
        await session.commit()

    try:
        yield session_factory
    finally:
        await engine.dispose()


async def test_catalog_endpoint_uses_service_with_stable_pagination(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/filmes",
                params={"genero": "drama", "tamanho_pagina": 1},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["meta"] == {
        "pagina": 1,
        "tamanho_pagina": 1,
        "total_itens": 2,
        "total_paginas": 2,
    }
    assert len(payload["itens"]) == 1
    assert payload["itens"][0]["id"] == "movie-1"
    assert payload["itens"][0]["nota_media"] == 8.5
    assert payload["itens"][0]["quantidade_avaliacoes"] == 1
    assert [genero["nome"] for genero in payload["itens"][0]["generos"]] == [
        "Drama",
        "Ficção científica",
    ]


async def test_catalog_endpoint_returns_public_error_for_invalid_pagination(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes", params={"pagina": 0})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "codigo": "REQUISICAO_INVALIDA",
        "mensagem": "Dados da requisição são inválidos.",
    }


async def test_catalog_endpoint_combines_case_insensitive_search_and_pagination(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with catalog_session_factory() as session:
        session.add(DimMovie(id_filme="movie-3", titulo="Chegada Final", ano_lancamento=2024))
        await session.commit()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/filmes",
                params={"busca": "CHEGADA", "pagina": 2, "tamanho_pagina": 1},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "itens": [
            {
                "id": "movie-3",
                "titulo": "Chegada Final",
                "ano_lancamento": 2024,
                "url_poster": None,
                "url_backdrop": None,
                "generos": [],
                "nota_media": None,
                "quantidade_avaliacoes": 0,
            }
        ],
        "meta": {
            "pagina": 2,
            "tamanho_pagina": 1,
            "total_itens": 2,
            "total_paginas": 2,
        },
    }


async def test_catalog_endpoint_finds_local_english_title_from_portuguese_query(
    catalog_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with catalog_session_factory() as session:
        session.add(
            DimMovie(id_filme="movie-spirited-away", titulo="Spirited Away", ano_lancamento=2001)
        )
        await session.commit()

    async def buscar_titulos_equivalentes(
        self: TmdbGateway, busca: str, ano: int | None = None
    ) -> set[str]:
        del self, busca, ano
        return {"a viagem de chihiro", "spirited away"}

    monkeypatch.setattr(TmdbGateway, "buscar_titulos_equivalentes", buscar_titulos_equivalentes)

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes", params={"busca": "A Viagem de Chihiro"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["itens"] == [
        {
            "id": "movie-spirited-away",
            "titulo": "Spirited Away",
            "ano_lancamento": 2001,
            "url_poster": None,
            "url_backdrop": None,
            "generos": [],
            "nota_media": None,
            "quantidade_avaliacoes": 0,
        }
    ]


async def test_catalog_endpoint_returns_an_empty_page_for_an_unknown_genre(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes", params={"genero": "Inexistente"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {
        "itens": [],
        "meta": {
            "pagina": 1,
            "tamanho_pagina": 12,
            "total_itens": 0,
            "total_paginas": 0,
        },
    }


async def test_catalog_endpoint_prioritizes_records_with_a_cover(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with catalog_session_factory() as session:
        session.add(
            DimMovie(
                id_filme="movie-cover",
                titulo="Zeta com imagem",
                ano_lancamento=2024,
                url_backdrop="https://example.com/backdrop.jpg",
            )
        )
        await session.commit()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes", params={"priorizar_capa": "true"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["itens"][0]["id"] == "movie-cover"


async def test_catalog_endpoint_prioritizes_records_with_a_trailer(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with catalog_session_factory() as session:
        session.add(
            DimMovie(id_filme="movie-no-trailer", titulo="A Sem trailer", ano_lancamento=2025)
        )
        await session.commit()

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/filmes", params={"priorizar_trailer": "true", "tamanho_pagina": 1}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["itens"][0]["id"] == "movie-1"


async def test_catalog_endpoint_can_return_only_records_with_a_trailer(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes", params={"somente_com_trailer": "true"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert [filme["id"] for filme in payload["itens"]] == ["movie-1"]
    assert payload["meta"]["total_itens"] == 1


async def test_trailer_endpoint_returns_the_saved_youtube_link(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes/movie-1/trailer")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"url_trailer": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}


async def test_catalog_endpoint_combines_advanced_filters(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/filmes",
                params={
                    "pessoa": "villeneuve",
                    "produtora": "paramount",
                    "ano_inicial": 2010,
                    "ano_final": 2020,
                    "duracao_minima": 110,
                    "duracao_maxima": 120,
                    "nota_minima": 8,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert [filme["id"] for filme in response.json()["itens"]] == ["movie-1"]


async def test_catalog_endpoint_excludes_unknown_duration_when_a_range_is_requested(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes", params={"duracao_minima": 117})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["itens"] == []


async def test_catalog_endpoint_rejects_an_invalid_year_range(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/filmes", params={"ano_inicial": 2025, "ano_final": 2020}
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


async def test_movie_detail_endpoint_returns_full_loaded_data(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes/movie-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == "movie-1"
    assert payload["nota_media"] == 8.5
    assert payload["quantidade_avaliacoes"] == 1
    assert [genero["nome"] for genero in payload["generos"]] == ["Drama", "Ficção científica"]
    assert {(pessoa["nome"], pessoa["papel"]) for pessoa in payload["pessoas"]} == {
        ("Denis Villeneuve", "Diretor"),
        ("Amy Adams", "Ator"),
    }
    assert payload["produtoras"][0]["nome"] == "Paramount Pictures"
    assert payload["desempenho"] == {
        "orcamento_usd": 47000000.0,
        "receita_usd": 203388186.0,
        "lucro_usd": 156388186.0,
        "orcamento_brl": 147921000.0,
        "receita_brl": 640673785.0,
        "lucro_brl": 492752785.0,
        "popularidade": 31.5,
        "nota_tmdb": 7.6,
        "quantidade_tmdb": 17200,
        "nota_imdb": 7.9,
        "quantidade_imdb": 780000,
    }
    assert payload["avaliacoes"][0]["nome"] == "Maria"
    assert payload["avaliacoes"][0]["nota"] == 8.5
    assert payload["avaliacoes"][0]["criada_em"]


async def test_movie_detail_endpoint_returns_not_found_for_unknown_movie(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/filmes/inexistente")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "codigo": "FILME_NAO_ENCONTRADO",
        "mensagem": "Filme não encontrado.",
    }


async def test_reviews_endpoints_create_history_and_keep_average_consistent(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            creation_response = await client.post(
                "/api/v1/filmes/movie-1/avaliacoes",
                json={
                    "nota": 10,
                    "comentario": "Uma avaliação excelente.",
                },
            )
            update_response = await client.post(
                "/api/v1/filmes/movie-1/avaliacoes",
                json={
                    "nota": 6,
                    "comentario": "Revendo a avaliação depois de alguns dias.",
                },
            )
            history_response = await client.get("/api/v1/filmes/movie-1/avaliacoes")
            mine_response = await client.get("/api/v1/filmes/movie-1/minha-avaliacao")
            detail_response = await client.get("/api/v1/filmes/movie-1")
            catalog_response = await client.get("/api/v1/filmes")
            removal_response = await client.delete("/api/v1/filmes/movie-1/minha-avaliacao")
            mine_after_removal = await client.get("/api/v1/filmes/movie-1/minha-avaliacao")
            detail_after_removal = await client.get("/api/v1/filmes/movie-1")
    finally:
        app.dependency_overrides.clear()

    assert creation_response.status_code == 201
    created = creation_response.json()
    assert created["id"]
    assert created["nota"] == 10
    assert created["criada_em"]
    assert update_response.status_code == 200
    assert update_response.json()["id"] == created["id"]
    assert update_response.json()["nota"] == 6
    assert mine_response.status_code == 200
    assert mine_response.json()["comentario"] == "Revendo a avaliação depois de alguns dias."
    assert history_response.status_code == 200
    assert [item["nome"] for item in history_response.json()] == ["Ana", "Maria"]
    assert detail_response.json()["quantidade_avaliacoes"] == 2
    assert detail_response.json()["nota_media"] == 7.25
    movie_in_catalog = next(
        item for item in catalog_response.json()["itens"] if item["id"] == "movie-1"
    )
    assert movie_in_catalog["quantidade_avaliacoes"] == 2
    assert movie_in_catalog["nota_media"] == 7.25
    assert removal_response.status_code == 204
    assert mine_after_removal.json() is None
    assert detail_after_removal.json()["quantidade_avaliacoes"] == 1
    assert detail_after_removal.json()["nota_media"] == 8.5


async def test_review_endpoints_validate_payload_and_return_not_found(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            invalid_score = await client.post(
                "/api/v1/filmes/movie-1/avaliacoes",
                json={"nota": 10.1, "comentario": "Inválida."},
            )
            invalid_text = await client.post(
                "/api/v1/filmes/movie-1/avaliacoes",
                json={"nota": 0, "comentario": " "},
            )
            missing_movie = await client.get("/api/v1/filmes/inexistente/avaliacoes")
    finally:
        app.dependency_overrides.clear()

    assert invalid_score.status_code == 422
    assert invalid_text.status_code == 422
    assert invalid_score.json() == {
        "codigo": "REQUISICAO_INVALIDA",
        "mensagem": "Dados da requisição são inválidos.",
    }
    assert missing_movie.status_code == 404
    assert missing_movie.json() == {
        "codigo": "FILME_NAO_ENCONTRADO",
        "mensagem": "Filme não encontrado.",
    }


async def test_private_reviews_do_not_appear_in_public_movie_history(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            created = await client.post(
                "/api/v1/filmes/movie-1/avaliacoes",
                json={
                    "nota": 8,
                    "comentario": "Uma resenha privada.",
                    "visibilidade": "privada",
                },
            )
            history = await client.get("/api/v1/filmes/movie-1/avaliacoes")
            detail = await client.get("/api/v1/filmes/movie-1")
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 201
    assert created.json()["visibilidade"] == "privada"
    assert [review["nome"] for review in history.json()] == ["Maria"]
    assert [review["nome"] for review in detail.json()["avaliacoes"]] == ["Maria"]


async def test_update_movie_endpoint_changes_only_sent_fields_and_relationships(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch(
                "/api/v1/filmes/movie-1",
                json={
                    "titulo": "A Chegada Atualizada",
                    "diretor": "Nova Diretora",
                    "generos": ["Drama"],
                    "atores": ["Novo Ator"],
                    "sinopse": None,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["titulo"] == "A Chegada Atualizada"
    assert payload["sinopse"] is None
    assert [genero["nome"] for genero in payload["generos"]] == ["Drama"]
    assert {(pessoa["nome"], pessoa["papel"]) for pessoa in payload["pessoas"]} == {
        ("Nova Diretora", "Diretor"),
        ("Novo Ator", "Ator"),
    }
    assert payload["produtoras"][0]["nome"] == "Paramount Pictures"
    assert payload["desempenho"]["nota_tmdb"] == 7.6


async def test_update_movie_endpoint_returns_not_found_for_unknown_movie(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.patch("/api/v1/filmes/inexistente", json={"titulo": "Novo"})
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


async def test_delete_movie_endpoint_removes_dependents_and_returns_no_content(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/filmes/movie-1")
            detail_response = await client.get("/api/v1/filmes/movie-1")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    assert detail_response.status_code == 404
    async with catalog_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DimMovie)) == 1
        assert await session.scalar(select(func.count()).select_from(DimReview)) == 0
        assert await session.scalar(select(func.count()).select_from(FactMoviePerformance)) == 0
        assert await session.scalar(select(func.count()).select_from(MovieReview)) == 0


async def test_delete_movie_endpoint_returns_not_found_for_unknown_movie(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.delete("/api/v1/filmes/inexistente")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


async def test_create_movie_endpoint_persists_required_relationships(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/filmes",
                json={
                    "titulo": "O Filme Criado",
                    "diretor": "Ana Diretora",
                    "ano_lancamento": 2025,
                    "generos": ["Drama", "Mistério"],
                    "sinopse": "Um filme cadastrado pela API.",
                    "atores": ["Bruno Ator"],
                    "roteiristas": ["Carla Roteirista"],
                    "produtoras": ["Estúdio Local"],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"].startswith("local-")
    assert payload["titulo"] == "O Filme Criado"
    assert {genero["nome"] for genero in payload["generos"]} == {"Drama", "Mistério"}
    assert {(pessoa["nome"], pessoa["papel"]) for pessoa in payload["pessoas"]} == {
        ("Ana Diretora", "Diretor"),
        ("Bruno Ator", "Ator"),
        ("Carla Roteirista", "Roteirista"),
    }
    assert payload["produtoras"] == [
        {"id": payload["produtoras"][0]["id"], "nome": "Estúdio Local"}
    ]

    async with catalog_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DimMovie)) == 3
        assert await session.scalar(select(func.count()).select_from(DimGenre)) == 3
        assert await session.scalar(select(func.count()).select_from(DimPerson)) == 5
        assert await session.scalar(select(func.count()).select_from(DimCompany)) == 2


async def test_create_movie_endpoint_rejects_incomplete_payload(
    catalog_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/filmes",
                json={
                    "titulo": "Sem diretor",
                    "generos": ["Drama"],
                    "sinopse": "Este cadastro deve falhar.",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json() == {
        "codigo": "REQUISICAO_INVALIDA",
        "mensagem": "Dados da requisição são inválidos.",
    }


async def test_create_movie_endpoint_rolls_back_and_hides_persistence_failure(
    catalog_session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def failing_commit(self: AsyncSession) -> None:
        del self
        raise SQLAlchemyError("falha simulada")

    async def override_db() -> AsyncIterator[AsyncSession]:
        async with catalog_session_factory() as session:
            yield session

    monkeypatch.setattr(AsyncSession, "commit", failing_commit)
    app.dependency_overrides[get_db] = override_db
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/filmes",
                json={
                    "titulo": "Filme que falha",
                    "diretor": "Diretora",
                    "ano_lancamento": 2024,
                    "generos": ["Drama"],
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 500
    assert response.json() == {
        "codigo": "FALHA_DE_PERSISTENCIA",
        "mensagem": "Não foi possível concluir a operação no momento.",
    }
    async with catalog_session_factory() as session:
        assert await session.scalar(select(func.count()).select_from(DimMovie)) == 2
