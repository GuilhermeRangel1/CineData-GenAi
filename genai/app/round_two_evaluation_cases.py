"""Casos tabulares do primeiro lote da rodada 2."""

from app.agent_models import ConversationContext
from app.evaluation_cases import EvaluationCase

ROUND_TWO_CLARIFICATIONS = {
    "Q36": r"bilheteria|receita|popularidade|nota|votos",
    "Q50": r"\b(?:filme|título|titulo|nome)\b",
}

_COMEDY_RANKING = ConversationContext(
    question="Quais foram as cinco comédias mais lucrativas de 2023?",
)
ROUND_TWO_CONTEXTS = {
    "Q47": (_COMEDY_RANKING,),
    "Q48": (_COMEDY_RANKING,),
    "Q49": (ConversationContext(
        question="Quais cinco animações de 2016 pra cá tiveram a maior bilheteria em reais?",
    ),),
}

ROUND_TWO_EVALUATIONS = (
    EvaluationCase(
        "Q25",
        "Que porcentagem da bilheteria total de 2023 veio dos dez filmes "
        "que mais arrecadaram naquele ano?",
        ("percentual_bilheteria",),
    ),
    EvaluationCase(
        "Q26",
        "Quais filmes tiveram os cinco maiores prejuízos de 2023?",
        ("titulo", "prejuizo_brl"),
    ),
    EvaluationCase(
        "Q27",
        "Quais filmes de animação que saíram no ano passado pelo menos se pagaram?",
        ("titulo",),
    ),
    EvaluationCase(
        "Q28",
        "Quais filmes de ação que já estrearam este ano têm orçamento e bilheteria informados?",
        ("titulo", "orcamento_brl", "receita_brl"),
    ),
    EvaluationCase(
        "Q29",
        "Dos cinco filmes mais caros de 2023, quais deram prejuízo "
        "e quanto faltou para se pagarem?",
        ("titulo", "prejuizo_brl"),
    ),
    EvaluationCase(
        "Q30",
        "Qual foi o orçamento mediano dos filmes de terror de 2024?",
        ("orcamento_mediano_brl",),
    ),
    EvaluationCase(
        "Q31",
        "Em quais anos a comédia teve mais estreias, mas o terror teve maior lucro médio? "
        "Conte todas as estreias, mesmo sem dados financeiros, e mostre as contagens "
        "e as médias dos dois gêneros.",
        (
            "ano_lancamento", "qtd_comedia", "qtd_terror",
            "lucro_medio_comedia", "lucro_medio_terror",
        ),
    ),
    EvaluationCase(
        "Q32",
        "Qual gênero mais aumentou a bilheteria total de 2022 para 2023, em reais?",
        ("nome_genero", "aumento_brl"),
    ),
    EvaluationCase(
        "Q33",
        "Quais filmes de 2023 ficaram no top 10 tanto em bilheteria quanto em lucro?",
        ("titulo", "receita_brl", "lucro_brl"),
    ),
    EvaluationCase(
        "Q34",
        "Em 2024, qual gênero teve a maior proporção de filmes com orçamento e "
        "bilheteria informados? Qual foi a porcentagem?",
        ("nome_genero", "percentual_informado"),
    ),
    EvaluationCase(
        "Q35",
        "Quanto as animações de 2023 arrecadaram para cada real de orçamento, somando tudo?",
        ("receita_por_real",),
    ),
    EvaluationCase(
        "Q36", "Quais filmes bombaram no ano passado?", (),
    ),
    EvaluationCase(
        "Q37",
        "Quantos filmes estrearam nos últimos cinco anos em cada gênero?",
        ("nome_genero", "total_filmes"),
    ),
    EvaluationCase("Q38", "Quem está no elenco de Barbie, de 2023?", ("nome_pessoa",)),
    EvaluationCase(
        "Q39", "Em que filmes Leonardo DiCaprio atuou sob direção de Martin Scorsese? "
        "Mostre o título e o ano de cada um.",
        ("titulo", "ano_lancamento"),
    ),
    EvaluationCase(
        "Q40", "Quais cinco duplas de atores fizeram mais filmes de terror juntas em 2023? "
        "Mostre quantos filmes fizeram juntos. Ponha os nomes de cada dupla em ordem "
        "alfabética antes de usar os nomes para desempatar o ranking.",
        ("ator_1", "ator_2", "total_filmes"),
    ),
    EvaluationCase(
        "Q41", "Quais diretores dirigiram pelo menos um filme de terror e um de comédia "
        "desde 2016? Mostre até dez nomes em ordem alfabética.",
        ("diretor",),
    ),
    EvaluationCase(
        "Q42", "Quais cinco produtoras fizeram mais coproduções em 2024? "
        "Mostre quantos filmes cada uma fez com pelo menos outra produtora.",
        ("nome_produtora", "total_coproducoes"),
    ),
    EvaluationCase(
        "Q43", "Das cinco produtoras com mais filmes de 2023, qual foi o filme de maior "
        "bilheteria de cada uma naquele ano? Mostre a bilheteria em reais.",
        ("nome_produtora", "titulo", "receita_brl"),
    ),
    EvaluationCase(
        "Q44", "Qual produtora trabalhou com o maior número de diretores diferentes em 2024? "
        "Mostre quantos diretores.",
        ("nome_produtora", "total_diretores"),
    ),
    EvaluationCase(
        "Q45", "Quais filmes de 2019 têm nota 8 ou mais e pelo menos 10 mil votos tanto "
        "no IMDb quanto no TMDB? Mostre as notas e os votos das duas fontes.",
        ("titulo", "nota_imdb", "qtd_imdb", "nota_tmdb", "qtd_tmdb"),
    ),
    EvaluationCase(
        "Q46", "Quais filmes saem do top 10 por nota no IMDb quando o mínimo sobe de mil "
        "para 10 mil votos? Mostre a nota e os votos, usando mais votos para desempatar.",
        ("titulo", "nota_imdb", "qtd_imdb"),
    ),
    EvaluationCase(
        "Q47", "E dessas aí, quais tiveram nota acima de 7 no IMDb?",
        ("titulo", "nota_imdb"),
    ),
    EvaluationCase("Q48", "Faz o mesmo pra terror.", ("titulo", "lucro_brl")),
    EvaluationCase("Q49", "Agora só de 2020 pra cá.", ("titulo", "receita_brl", "ano_lancamento")),
    EvaluationCase("Q50", "Quem dirigiu esse filme?", ()),
)
