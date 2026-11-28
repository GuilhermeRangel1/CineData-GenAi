"""Additional evaluation cases kept separate from the original requirements."""

from app.evaluation_cases import EvaluationCase

EXPANSION_EVALUATIONS = (
    EvaluationCase(
        "Q15", "Quais os dez documentários de 2016 a 2024 com a maior nota no IMDb "
        "e pelo menos mil votos? Em notas iguais, priorize quem tem mais votos. "
        "Mostre título, ano, nota e votos.",
        ("titulo", "ano_lancamento", "nota_imdb", "qtd_imdb"),
    ),
    EvaluationCase(
        "Q16", "De 2016 a 2024, em quais anos saíram mais filmes de terror do que de "
        "comédia? Mostre as duas contagens e a diferença em cada ano.",
        ("ano_lancamento", "terror", "comedia", "diferenca"),
    ),
    EvaluationCase(
        "Q17", "Entre os filmes que custaram até 10 milhões de reais, quais foram os cinco "
        "com maior lucro? Mostre título, orçamento, receita e lucro em reais.",
        ("titulo", "orcamento_brl", "receita_brl", "lucro_brl"),
    ),
    EvaluationCase(
        "Q18", "Quais os cinco filmes com maior nota no IMDb entre os que têm pelo menos "
        "5 mil votos no IMDb, ao menos um voto no TMDB e nota no TMDB pelo menos um ponto menor? "
        "Em notas IMDb iguais, priorize quem tem mais votos no IMDb. "
        "Mostre título, as duas notas, votos no IMDb e a diferença.",
        ("titulo", "nota_imdb", "nota_tmdb", "qtd_imdb", "diferenca"),
    ),
    EvaluationCase(
        "Q19", "De 2016 a 2024, em qual ano as animações tiveram a maior nota média "
        "no IMDb? Só considere anos com pelo menos dez filmes avaliados. "
        "Mostre ano, média e quantidade de filmes.",
        ("ano_lancamento", "nota_media_imdb", "filmes_avaliados"),
    ),
    EvaluationCase(
        "Q20", "Quais diretores trabalharam com Leonardo DiCaprio em pelo menos dois filmes? "
        "Mostre quantos fizeram juntos, quantos têm avaliação válida no IMDb e a média "
        "dessas notas, ordenando pela maior média.",
        ("diretor", "filmes_em_comum", "filmes_avaliados", "nota_media_imdb"),
    ),
    EvaluationCase(
        "Q21", "Quais três gêneros tiveram o maior lucro médio em reais de 2016 a 2024? "
        "Use lucro como receita menos orçamento, só com os dois valores informados. "
        "Mostre, nesta ordem: gênero, lucro médio, número de filmes na conta "
        "e percentual que deu lucro.",
        ("nome_genero", "lucro_medio_brl", "filmes_elegiveis", "percentual_lucrativo"),
    ),
    EvaluationCase(
        "Q22", "Dos filmes de ficção científica de 2016 a 2024 com orçamento e receita "
        "informados, quantos deram lucro? Mostre o total elegível, quantos deram lucro "
        "e a porcentagem.",
        ("filmes_elegiveis", "filmes_lucrativos", "percentual_lucrativo"),
    ),
    EvaluationCase(
        "Q23", "Entre produtoras com dez ou mais filmes com orçamento e receita conhecidos, "
        "quais as cinco com a maior porcentagem de filmes lucrativos? Mostre o total elegível, "
        "quantos deram lucro, a porcentagem e o lucro mediano em reais.",
        ("nome_produtora", "filmes_elegiveis", "filmes_lucrativos",
         "percentual_lucrativo", "lucro_mediano_brl"),
    ),
    EvaluationCase(
        "Q24", "Desde 2016, quais filmes já lançados têm nota IMDb de pelo menos 8, "
        "10 mil votos ou mais e receita acima do dobro do orçamento positivo? "
        "Mostre os dez de maior lucro, com título, ano, nota, votos e lucro em reais.",
        ("titulo", "ano_lancamento", "nota_imdb", "qtd_imdb", "lucro_brl"),
    ),
)
