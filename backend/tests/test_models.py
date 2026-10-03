from app.communities import models as community_models  # noqa: F401  Registra os modelos ORM.
from app.conversations import models as conversation_models  # noqa: F401  Registra os modelos ORM.
from app.db.base import Base
from app.movies import models  # noqa: F401  Registra os modelos ORM.
from app.users import models as user_models  # noqa: F401  Registra os modelos ORM.


def test_movie_schema_registers_expected_tables() -> None:
    expected_tables = {
        "bridge_movie_company",
        "bridge_movie_genre",
        "bridge_movie_person",
        "dim_companies",
        "dim_genres",
        "dim_movies",
        "dim_people",
        "dim_reviews",
        "fact_movies_performance",
        "movie_reviews",
        "users",
        "user_lists",
        "user_list_movies",
        "watch_later_movies",
        "friendship_requests",
        "communities",
        "community_memberships",
        "community_posts",
        "community_comments",
        "community_reactions",
        "gold_database_sync",
        "chat_conversations",
        "chat_messages",
    }

    assert set(Base.metadata.tables) == expected_tables
    assert "idioma_original" in Base.metadata.tables["dim_movies"].columns


def test_movie_review_columns_match_gold_and_application_schema() -> None:
    table = Base.metadata.tables["movie_reviews"]

    assert {"sk_movie_review_id", "sk_movie_id", "nome", "nota", "comentario"} <= set(
        table.columns.keys()
    )
    assert "visibilidade" in table.columns
    assert table.primary_key.columns.keys() == ["sk_movie_review_id"]


def test_user_schema_stores_only_a_password_hash() -> None:
    table = Base.metadata.tables["users"]

    assert {"id", "email", "nome", "password_hash", "role"} <= set(table.columns.keys())
    assert "password" not in table.columns
    assert table.primary_key.columns.keys() == ["id"]


def test_chat_schema_keeps_messages_ordered_inside_each_conversation() -> None:
    conversations = Base.metadata.tables["chat_conversations"]
    messages = Base.metadata.tables["chat_messages"]

    assert {"id", "user_id", "titulo", "created_at", "updated_at"} <= set(
        conversations.columns.keys()
    )
    assert {"conversation_id", "position", "role", "content", "response_data"} <= set(
        messages.columns.keys()
    )
    assert messages.primary_key.columns.keys() == ["id"]
