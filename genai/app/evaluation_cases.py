"""Casos locais para avaliar as perguntas obrigatórias da atividade."""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class EvaluationCase:
    """Contrato de uma pergunta e do resultado tabular que ela deve produzir."""

    query_id: str
    question: str
    expected_columns: tuple[str, ...]
    metric: str | None = None
    unit: str | None = None
    period: str | None = None
    population: str | None = None
    limitations: str | None = None


MANDATORY_EVALUATIONS: tuple[EvaluationCase, ...] = (
    EvaluationCase(
        "Q01",
        "Quais são os 10 filmes com maior receita em BRL?",
        ("sk_movie_id", "titulo", "receita_brl"),
        metric="receita por filme",
        unit="BRL",
        period="todo o Gold disponível",
        population="filmes com receita_brl não nula",
        limitations="não exige orçamento e mantém desempate estável por título e chave técnica",
    ),
    EvaluationCase(
        "Q02",
        "Qual é o lucro médio em BRL por gênero?",
        ("nome_genero", "filmes_elegiveis", "lucro_medio_brl"),
        metric="lucro médio por gênero",
        unit="BRL por filme",
        period="todo o Gold disponível",
        population="filmes com receita_brl e orcamento_brl não nulos",
        limitations=(
            "lucro é calculado como receita menos orçamento; filmes com vários gêneros "
            "participam uma vez em cada gênero"
        ),
    ),
    EvaluationCase(
        "Q03",
        "Quais filmes têm as maiores margens de lucro?",
        ("sk_movie_id", "titulo", "margem"),
        metric="margem de lucro por filme",
        unit="fração, com exibição possível em percentual",
        period="todo o Gold disponível",
        population="filmes com receita_brl e orcamento_brl não nulos e receita_brl maior que zero",
        limitations="margem é calculada como (receita menos orçamento) dividido pela receita",
    ),
    EvaluationCase(
        "Q04",
        "Quais são os 5 filmes mais populares?",
        ("sk_movie_id", "titulo", "popularidade"),
        metric="popularidade por filme",
        unit="pontuação de popularidade",
        period="todo o Gold disponível",
        population="filmes com popularidade não nula",
        limitations=(
            "popularidade é uma pontuação do Gold, não contagem real de visualizações; "
            "zero é válido e não deve ser tratado como ausência"
        ),
    ),
    EvaluationCase(
        "Q05",
        "Em quais filmes há maior divergência entre as notas TMDB e IMDb?",
        ("sk_movie_id", "titulo", "divergencia", "nota_tmdb", "qtd_tmdb", "nota_imdb", "qtd_imdb"),
        metric="diferença absoluta entre notas TMDB e IMDb",
        unit="pontos em escala de 0 a 10",
        period="todo o Gold disponível",
        population="filmes com ambas as notas não nulas e contagens de votos positivas",
        limitations=(
            "não aplica corte arbitrário de votos e exibe as contagens para contextualização"
        ),
    ),
    EvaluationCase(
        "Q06",
        "Qual é a nota IMDb média por ano de lançamento?",
        ("ano_lancamento", "filmes_validos", "nota_imdb_media"),
        metric="média IMDb por ano de lançamento",
        unit="pontuação em escala de 0 a 10",
        period="do primeiro lançamento disponível até a data atual",
        population=(
            "filmes lançados até a data atual com nota_imdb não nula e qtd_imdb positiva"
        ),
        limitations=(
            "média simples por filme; lançamentos futuros são excluídos e a quantidade "
            "de filmes válidos é informada por ano"
        ),
    ),
    EvaluationCase(
        "Q07",
        "Qual ator participou de mais filmes nos últimos cinco anos?",
        ("sk_person_id", "nome_pessoa", "total_filmes"),
        metric="quantidade de filmes por ator",
        unit="filmes distintos",
        period="janela móvel dos cinco anos anteriores à data atual",
        population="pessoas do tipo Ator com data_lancamento válida dentro da janela",
        limitations=(
            "a associação reflete os créditos existentes no Gold e não distingue "
            + "elenco principal"
        ),
    ),
    EvaluationCase(
        "Q08",
        "Quais diretores têm a maior nota IMDb média considerando no mínimo cinco filmes?",
        ("sk_person_id", "nome_pessoa", "filmes_validos", "nota_media"),
        metric="média IMDb por diretor",
        unit="pontuação em escala de 0 a 10",
        period="todo o Gold disponível",
        population="diretores com pelo menos cinco filmes com nota IMDb e votos positivos",
        limitations="a média usa IMDb e empates seguem ordenação estável por nome e chave técnica",
    ),
    EvaluationCase(
        "Q09",
        "Qual dupla de ator e diretor trabalhou junta em mais filmes?",
        ("ator", "diretor", "filmes_em_comum"),
        metric="coocorrência de filmes por dupla de ator e diretor",
        unit="filmes distintos em comum",
        period="todo o Gold disponível",
        population="filmes associados simultaneamente a uma pessoa Ator e uma pessoa Diretor",
        limitations="coocorrência não comprova crédito principal nem ordem dos créditos",
    ),
    EvaluationCase(
        "Q10",
        "Quantos filmes existem associados a cada gênero?",
        ("nome_genero", "total_filmes"),
        metric="quantidade de filmes por gênero",
        unit="filmes distintos",
        period="todo o Gold disponível",
        population="associações válidas entre filmes e gêneros",
        limitations="filmes multigênero participam uma vez em cada gênero",
    ),
    EvaluationCase(
        "Q11",
        "Qual produtora acumulou o maior lucro total em BRL?",
        ("sk_company_id", "nome_produtora", "filmes_elegiveis", "lucro_total_brl"),
        metric="lucro total por produtora",
        unit="BRL",
        period="todo o Gold disponível",
        population="filmes associados à produtora com receita_brl e orcamento_brl não nulos",
        limitations="o lucro integral de um filme é atribuído a cada produtora associada",
    ),
    EvaluationCase(
        "Q12",
        "Qual gênero tem a maior margem média de lucro?",
        ("sk_genre_id", "nome_genero", "filmes_validos", "margem_media"),
        metric="margem média por gênero",
        unit="fração, com exibição possível em percentual",
        period="todo o Gold disponível",
        population="filmes com receita e orçamento válidos e receita maior que zero",
        limitations=" ".join(
            (
                "é a média das margens por filme; não é margem calculada sobre totais",
                "agregados",
            )
        ),
    ),
    EvaluationCase(
        "Q13",
        "Quais filmes têm a maior quantidade de avaliações de usuários?",
        ("sk_movie_id", "titulo", "qtd_avaliacoes_usuarios"),
        metric="quantidade de avaliações de usuários por filme",
        unit="avaliações",
        period="todo o Gold disponível",
        population="filmes com resumo em dim_reviews",
        limitations=(
            "usa a contagem resumida por filme e não infere usuários únicos a partir "
            "de movie_reviews"
        ),
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
        metric="diferença absoluta entre média de usuários e nota IMDb",
        unit="pontos em escala de 0 a 10",
        period="todo o Gold disponível",
        population=" ".join(
            (
                "filmes com média de usuários, quantidade positiva e nota IMDb com votos",
                "positivos",
            )
        ),
        limitations="não aplica corte arbitrário de votos e usa o resumo de avaliações por filme",
    ),
)


def _normalize_question(question: str) -> str:
    """Normaliza espaços e caixa para reconhecer a formulação obrigatória."""

    return re.sub(r"\s+", " ", question.strip().casefold())


def find_evaluation_case(question: str) -> EvaluationCase | None:
    """Encontra o contrato de uma pergunta obrigatória em sua formulação canônica."""

    normalized = _normalize_question(question)
    return next(
        (
            case
            for case in MANDATORY_EVALUATIONS
            if _normalize_question(case.question) == normalized
        ),
        None,
    )


def get_evaluation_case(query_id: str) -> EvaluationCase:
    """Retorna um caso obrigatório pelo identificador da consulta de referência."""

    for case in MANDATORY_EVALUATIONS:
        if case.query_id == query_id:
            return case
    raise KeyError(f"Caso de avaliação desconhecido: {query_id}")
