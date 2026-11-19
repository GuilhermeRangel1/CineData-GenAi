"""Reformulações de avaliação mantidas fora das instruções do agente."""

EVALUATION_PARAPHRASES = {
    "Q01": (
        "Me mostra os dez filmes que mais arrecadaram em reais.",
    ),
    "Q02": (
        "Na média, quanto os filmes de cada gênero deram de lucro em reais?",
    ),
    "Q03": (
        "Quais são os dez títulos que ficaram com a maior margem de lucro?",
    ),
    "Q04": (
        "Me passa os cinco títulos com a maior pontuação de popularidade.",
    ),
    "Q05": (
        "Em quais dez filmes as notas do IMDb e do TMDB mais destoam? Mostra as notas, os votos "
        "de cada site e a diferença em pontos.",
    ),
    "Q06": (
        "Pra cada ano de estreia, quanto deu a média das notas no IMDb e quantos filmes avaliados "
        "entraram na conta? Só os que já saíram.",
    ),
    "Q07": (
        "Quem do elenco apareceu em mais filmes nos últimos cinco anos? Mostra a quantidade e "
        "inclui quem empatou na liderança.",
    ),
    "Q08": (
        "Quem lidera em média de nota do IMDb na direção, contando só quem dirigiu ao menos cinco "
        "filmes avaliados? Se empatar, mostra todos, com a média e a quantidade.",
    ),
    "Q09": (
        "Que ator e diretor mais repetiram parceria? Mostra quantos filmes fizeram juntos e "
        "inclui empates no topo.",
    ),
    "Q10": (
        "De cada gênero, quantos filmes a gente tem no catálogo?",
    ),
    "Q11": (
        "Qual produtora juntou mais lucro em reais somando os filmes dela? Mostra o lucro e "
        "quantos filmes entraram na conta, incluindo empates no topo.",
    ),
    "Q12": (
        "Qual gênero lidera se eu tirar a média das margens de cada filme? Mostra a margem média "
        "e quantos filmes entraram, incluindo empates no topo.",
    ),
    "Q13": (
        "Quais títulos receberam mais avaliações dos usuários? Mostra a contagem e inclui todos "
        "os empatados em primeiro.",
    ),
    "Q14": (
        "Em que filme a nota média dos usuários ficou mais distante da do IMDb? Mostra as duas "
        "notas, as contagens, a diferença e qualquer empate no topo.",
    ),
    "Q15": (
        "Dos docs que saíram entre 2016 e 2024, quais dez foram mais bem avaliados no IMDb? Só os "
        "com mil votos ou mais. Se a nota empatar, vai pelo mais votado. Quero título, ano, nota "
        "e votos.",
        "Faz um top 10 de documentários pela nota do IMDb, de 2016 a 2024, com no mínimo mil "
        "votos. Usa votos pra desempatar e inclui filme, ano, nota e total de votos.",
    ),
    "Q16": (
        "Entre 2016 e 2024, terror chegou a passar comédia em número de estreias em algum ano? Se "
        "passou, me diz o ano, quantos saíram de cada um e por quanto.",
        "De 2016 até 2024, mostra só os anos em que estreou mais terror que comédia, com o total "
        "de cada gênero e a diferença.",
    ),
    "Q17": (
        "Pega os filmes que custaram no máximo R$ 10 milhões e me diz os cinco que mais lucraram. "
        "Quero nome, quanto custou, quanto arrecadou e o lucro, tudo em reais.",
        "Entre os títulos que custaram até dez milhões de reais, quais cinco ficaram com o maior "
        "lucro? Lista filme, orçamento, bilheteria e lucro em reais.",
    ),
    "Q18": (
        "Me dá o top 5 por nota IMDb entre filmes com 5 mil votos ou mais lá e pelo menos um voto "
        "no TMDB, mas que tiraram pelo menos um ponto a menos no TMDB. Desempata pelos votos do "
        "IMDb e mostra título, as duas notas, votos IMDb e diferença.",
        "Quais são os cinco mais bem avaliados no IMDb com 5 mil votos pra cima, se no TMDB "
        "tiverem pelo menos um voto e a nota for pelo menos um ponto menor? Em empate, prioriza "
        "mais votos no IMDb. Mostra filme, notas, votos do IMDb e diferença.",
    ),
    "Q19": (
        "De 2016 a 2024, qual ano mandou melhor na média do IMDb pras animações? Ignora ano com "
        "menos de dez animações avaliadas e diz o ano, a média e quantas entraram.",
        "Em qual ano entre 2016 e 2024 as animações tiveram a melhor média no IMDb? Só vale ano "
        "com dez ou mais títulos avaliados. Inclui ano, nota média e total avaliado.",
    ),
    "Q20": (
        "Quem dirigiu o Leonardo DiCaprio duas vezes ou mais? Diz quantos filmes fizeram juntos, "
        "quantos têm nota válida no IMDb e a média dessas notas. Coloca a maior média primeiro.",
        "Quais diretores fizeram pelo menos dois filmes com o DiCaprio? Pra cada um, quero o "
        "total de filmes juntos, quantos têm avaliação válida no IMDb e a média lá, da maior pra "
        "menor.",
    ),
    "Q21": (
        "Entre 2016 e 2024, quais três gêneros ficaram no topo em lucro médio? Faz a conta em "
        "reais tirando o orçamento da bilheteria, só com os dois informados. Mostra gênero, "
        "média, total que entrou e porcentagem que deu lucro, nessa ordem.",
        "De 2016 a 2024, me dá o top 3 gêneros pela média de receita menos orçamento em reais. Só "
        "usa filmes com os dois valores. Quero gênero, lucro médio, quantidade incluída e "
        "percentual lucrativo, nessa ordem.",
    ),
    "Q22": (
        "Dos sci-fi que saíram de 2016 a 2024 e têm custo e bilheteria no catálogo, quantos deram "
        "lucro? Me passa o total com esses dados, quantos lucraram e a porcentagem.",
        "De 2016 até 2024, que parte dos filmes de ficção científica deu lucro? Conta só os com "
        "orçamento e receita informados e diz o total, quantos lucraram e o percentual.",
    ),
    "Q23": (
        "Quais cinco produtoras tiveram a maior fatia de filmes no lucro? Só vale quem tiver dez "
        "ou mais filmes com custo e bilheteria registrados. Mostra quantos entram na conta, "
        "quantos lucraram, a porcentagem e a mediana do lucro em reais.",
        "Me passa as cinco produtoras com a melhor taxa de filmes lucrativos, dentre as que têm "
        "pelo menos dez títulos com receita e orçamento. Quero total elegível, total com lucro, "
        "percentual e lucro mediano em reais.",
    ),
    "Q24": (
        "De 2016 pra cá, dos filmes que já estrearam, quais dez mais lucraram em reais com nota 8 "
        "pra cima e pelo menos 10 mil votos no IMDb? Só vale orçamento positivo e bilheteria "
        "acima de duas vezes o custo. Mostra filme, ano, nota, votos e lucro.",
        "Desde 2016, faz um top 10 por lucro dos filmes já lançados com IMDb de pelo menos 8 e 10 "
        "mil votos ou mais. Filtra os de orçamento positivo que arrecadaram mais que o dobro "
        "dele. Inclui título, ano, nota, votos e lucro em reais.",
    ),
}
