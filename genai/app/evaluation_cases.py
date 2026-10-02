"""Casos locais para avaliar as perguntas obrigatórias da atividade."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCase:
    """Contrato de uma pergunta e do resultado tabular que ela deve produzir."""

    query_id: str
    question: str
    expected_columns: tuple[str, ...]


MANDATORY_EVALUATIONS: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        "Q01",
        "Quais são os 10 filmes com maior receita em BRL?",
        ("sk_movie_id", "titulo", "receita_brl"),
    ),
    EvaluationCase(
        "Q02",
        "Qual é o lucro médio em BRL por gênero?",
        ("nome_genero", "filmes_elegiveis", "lucro_medio_brl"),
    ),
    EvaluationCase(
        "Q03",
        "Quais filmes têm as maiores margens de lucro?",
        ("sk_movie_id", "titulo", "margem"),
    ),
    EvaluationCase(
        "Q04",
        "Quais são os 5 filmes mais populares?",
        ("sk_movie_id", "titulo", "popularidade"),
    ),
    EvaluationCase(
        "Q05",
        "Em quais filmes há maior divergência entre as notas TMDB e IMDb?",
        ("sk_movie_id", "titulo", "divergencia", "nota_tmdb", "qtd_tmdb", "nota_imdb", "qtd_imdb"),
    ),
    EvaluationCase(
        "Q06",
        "Qual é a nota IMDb média por ano de lançamento?",
        ("ano_lancamento", "filmes_validos", "nota_imdb_media"),
    ),
    EvaluationCase(
        "Q07",
        "Qual ator participou de mais filmes nos últimos cinco anos?",
        ("sk_person_id", "nome_pessoa", "total_filmes"),
    ),
    EvaluationCase(
        "Q08",
        "Quais diretores têm a maior nota IMDb média considerando no mínimo cinco filmes?",
        ("sk_person_id", "nome_pessoa", "filmes_validos", "nota_media"),
    ),
    EvaluationCase(
        "Q09",
        "Qual dupla de ator e diretor trabalhou junta em mais filmes?",
        ("ator", "diretor", "filmes_em_comum"),
    ),
    EvaluationCase(
        "Q10",
        "Quantos filmes existem associados a cada gênero?",
        ("nome_genero", "total_filmes"),
    ),
    EvaluationCase(
        "Q11",
        "Qual produtora acumulou o maior lucro total em BRL?",
        ("sk_company_id", "nome_produtora", "filmes_elegiveis", "lucro_total_brl"),
    ),
    EvaluationCase(
        "Q12",
        "Qual gênero tem a maior margem média de lucro?",
        ("sk_genre_id", "nome_genero", "filmes_validos", "margem_media"),
    ),
    EvaluationCase(
        "Q13",
        "Quais filmes têm a maior quantidade de avaliações de usuários?",
        ("sk_movie_id", "titulo", "qtd_avaliacoes_usuarios"),
    ),
    EvaluationCase(
        "Q14",
        "Qual filme tem a maior divergência entre a média dos usuários e a nota IMDb?",
        (
            "sk_movie_id",
            "titulo",
            "nota_media_usuarios",
            "nota_imdb",
            "qtd_avaliacoes_usuarios",
            "qtd_imdb",
            "divergencia",
        ),
    ),
)


def get_evaluation_case(query_id: str) -> EvaluationCase:
    """Retorna um caso obrigatório pelo identificador da consulta de referência."""

    for case in MANDATORY_EVALUATIONS:
        if case.query_id == query_id:
            return case
    raise KeyError(f"Caso de avaliação desconhecido: {query_id}")
