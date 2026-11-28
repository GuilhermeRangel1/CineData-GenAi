# Casos de avaliação das perguntas obrigatórias

A suíte reúne os 50 casos oficiais de Q01 a Q50. Os resultados tabulares são comparados com as consultas de referência de cada lote. Q36 e Q50 esperam um pedido de esclarecimento.

## Q01–Q14

[SQL de referência](reference-queries.sql)

| Caso | Pergunta oficial | Colunas esperadas |
| --- | --- | --- |
| Q01 | Quais são os 10 filmes com maior receita em BRL? | `sk_movie_id`, `titulo`, `receita_brl` |
| Q02 | Qual é o lucro médio em BRL por gênero? | `nome_genero`, `filmes_elegiveis`, `lucro_medio_brl` |
| Q03 | Quais filmes têm as maiores margens de lucro? | `sk_movie_id`, `titulo`, `margem` |
| Q04 | Quais são os 5 filmes mais populares? | `sk_movie_id`, `titulo`, `popularidade` |
| Q05 | Em quais filmes há maior divergência entre as notas TMDB e IMDb? | `sk_movie_id`, `titulo`, `divergencia`, `nota_tmdb`, `qtd_tmdb`, `nota_imdb`, `qtd_imdb` |
| Q06 | Qual é a nota IMDb média por ano de lançamento? | `ano_lancamento`, `filmes_validos`, `nota_imdb_media` |
| Q07 | Qual ator participou de mais filmes nos últimos cinco anos? | `sk_person_id`, `nome_pessoa`, `total_filmes` |
| Q08 | Quais diretores têm a maior nota IMDb média considerando no mínimo cinco filmes? | `sk_person_id`, `nome_pessoa`, `filmes_validos`, `nota_media` |
| Q09 | Qual dupla de ator e diretor trabalhou junta em mais filmes? | `ator`, `diretor`, `filmes_em_comum` |
| Q10 | Quantos filmes existem associados a cada gênero? | `nome_genero`, `total_filmes` |
| Q11 | Qual produtora acumulou o maior lucro total em BRL? | `sk_company_id`, `nome_produtora`, `filmes_elegiveis`, `lucro_total_brl` |
| Q12 | Qual gênero tem a maior margem média de lucro? | `sk_genre_id`, `nome_genero`, `filmes_validos`, `margem_media` |
| Q13 | Quais filmes têm a maior quantidade de avaliações de usuários? | `sk_movie_id`, `titulo`, `qtd_avaliacoes_usuarios` |
| Q14 | Qual filme tem a maior divergência entre a média dos usuários e a nota IMDb? | `sk_movie_id`, `titulo`, `nota_media_usuarios`, `nota_imdb`, `qtd_avaliacoes_usuarios`, `qtd_imdb`, `divergencia` |

## Q15–Q24

[SQL de referência](expansion-reference-queries.sql)

| Caso | Pergunta oficial | Colunas esperadas |
| --- | --- | --- |
| Q15 | Quais os dez documentários de 2016 a 2024 com a maior nota no IMDb e pelo menos mil votos? Em notas iguais, priorize quem tem mais votos. Mostre título, ano, nota e votos. | `titulo`, `ano_lancamento`, `nota_imdb`, `qtd_imdb` |
| Q16 | De 2016 a 2024, em quais anos saíram mais filmes de terror do que de comédia? Mostre as duas contagens e a diferença em cada ano. | `ano_lancamento`, `terror`, `comedia`, `diferenca` |
| Q17 | Entre os filmes que custaram até 10 milhões de reais, quais foram os cinco com maior lucro? Mostre título, orçamento, receita e lucro em reais. | `titulo`, `orcamento_brl`, `receita_brl`, `lucro_brl` |
| Q18 | Quais os cinco filmes com maior nota no IMDb entre os que têm pelo menos 5 mil votos no IMDb, ao menos um voto no TMDB e nota no TMDB pelo menos um ponto menor? Em notas IMDb iguais, priorize quem tem mais votos no IMDb. Mostre título, as duas notas, votos no IMDb e a diferença. | `titulo`, `nota_imdb`, `nota_tmdb`, `qtd_imdb`, `diferenca` |
| Q19 | De 2016 a 2024, em qual ano as animações tiveram a maior nota média no IMDb? Só considere anos com pelo menos dez filmes avaliados. Mostre ano, média e quantidade de filmes. | `ano_lancamento`, `nota_media_imdb`, `filmes_avaliados` |
| Q20 | Quais diretores trabalharam com Leonardo DiCaprio em pelo menos dois filmes? Mostre quantos fizeram juntos, quantos têm avaliação válida no IMDb e a média dessas notas, ordenando pela maior média. | `diretor`, `filmes_em_comum`, `filmes_avaliados`, `nota_media_imdb` |
| Q21 | Quais três gêneros tiveram o maior lucro médio em reais de 2016 a 2024? Use lucro como receita menos orçamento, só com os dois valores informados. Mostre, nesta ordem: gênero, lucro médio, número de filmes na conta e percentual que deu lucro. | `nome_genero`, `lucro_medio_brl`, `filmes_elegiveis`, `percentual_lucrativo` |
| Q22 | Dos filmes de ficção científica de 2016 a 2024 com orçamento e receita informados, quantos deram lucro? Mostre o total elegível, quantos deram lucro e a porcentagem. | `filmes_elegiveis`, `filmes_lucrativos`, `percentual_lucrativo` |
| Q23 | Entre produtoras com dez ou mais filmes com orçamento e receita conhecidos, quais as cinco com a maior porcentagem de filmes lucrativos? Mostre o total elegível, quantos deram lucro, a porcentagem e o lucro mediano em reais. | `nome_produtora`, `filmes_elegiveis`, `filmes_lucrativos`, `percentual_lucrativo`, `lucro_mediano_brl` |
| Q24 | Desde 2016, quais filmes já lançados têm nota IMDb de pelo menos 8, 10 mil votos ou mais e receita acima do dobro do orçamento positivo? Mostre os dez de maior lucro, com título, ano, nota, votos e lucro em reais. | `titulo`, `ano_lancamento`, `nota_imdb`, `qtd_imdb`, `lucro_brl` |

## Q25–Q50

[SQL de referência](round-two-reference-queries.sql)

| Caso | Pergunta oficial | Colunas esperadas |
| --- | --- | --- |
| Q25 | Que porcentagem da bilheteria total de 2023 veio dos dez filmes que mais arrecadaram naquele ano? | `percentual_bilheteria` |
| Q26 | Quais filmes tiveram os cinco maiores prejuízos de 2023? | `titulo`, `prejuizo_brl` |
| Q27 | Quais filmes de animação que saíram no ano passado pelo menos se pagaram? | `titulo` |
| Q28 | Quais filmes de ação que já estrearam este ano têm orçamento e bilheteria informados? | `titulo`, `orcamento_brl`, `receita_brl` |
| Q29 | Dos cinco filmes mais caros de 2023, quais deram prejuízo e quanto faltou para se pagarem? | `titulo`, `prejuizo_brl` |
| Q30 | Qual foi o orçamento mediano dos filmes de terror de 2024? | `orcamento_mediano_brl` |
| Q31 | Em quais anos a comédia teve mais estreias, mas o terror teve maior lucro médio? Conte todas as estreias, mesmo sem dados financeiros, e mostre as contagens e as médias dos dois gêneros. | `ano_lancamento`, `qtd_comedia`, `qtd_terror`, `lucro_medio_comedia`, `lucro_medio_terror` |
| Q32 | Qual gênero mais aumentou a bilheteria total de 2022 para 2023, em reais? | `nome_genero`, `aumento_brl` |
| Q33 | Quais filmes de 2023 ficaram no top 10 tanto em bilheteria quanto em lucro? | `titulo`, `receita_brl`, `lucro_brl` |
| Q34 | Em 2024, qual gênero teve a maior proporção de filmes com orçamento e bilheteria informados? Qual foi a porcentagem? | `nome_genero`, `percentual_informado` |
| Q35 | Quanto as animações de 2023 arrecadaram para cada real de orçamento, somando tudo? | `receita_por_real` |
| Q36 | Quais filmes bombaram no ano passado? | Pedido de esclarecimento |
| Q37 | Quantos filmes estrearam nos últimos cinco anos em cada gênero? | `nome_genero`, `total_filmes` |
| Q38 | Quem está no elenco de Barbie, de 2023? | `nome_pessoa` |
| Q39 | Em que filmes Leonardo DiCaprio atuou sob direção de Martin Scorsese? Mostre o título e o ano de cada um. | `titulo`, `ano_lancamento` |
| Q40 | Quais cinco duplas de atores fizeram mais filmes de terror juntas em 2023? Mostre quantos filmes fizeram juntos. Ponha os nomes de cada dupla em ordem alfabética antes de usar os nomes para desempatar o ranking. | `ator_1`, `ator_2`, `total_filmes` |
| Q41 | Quais diretores dirigiram pelo menos um filme de terror e um de comédia desde 2016? Mostre até dez nomes em ordem alfabética. | `diretor` |
| Q42 | Quais cinco produtoras fizeram mais coproduções em 2024? Mostre quantos filmes cada uma fez com pelo menos outra produtora. | `nome_produtora`, `total_coproducoes` |
| Q43 | Das cinco produtoras com mais filmes de 2023, qual foi o filme de maior bilheteria de cada uma naquele ano? Mostre a bilheteria em reais. | `nome_produtora`, `titulo`, `receita_brl` |
| Q44 | Qual produtora trabalhou com o maior número de diretores diferentes em 2024? Mostre quantos diretores. | `nome_produtora`, `total_diretores` |
| Q45 | Quais filmes de 2019 têm nota 8 ou mais e pelo menos 10 mil votos tanto no IMDb quanto no TMDB? Mostre as notas e os votos das duas fontes. | `titulo`, `nota_imdb`, `qtd_imdb`, `nota_tmdb`, `qtd_tmdb` |
| Q46 | Quais filmes saem do top 10 por nota no IMDb quando o mínimo sobe de mil para 10 mil votos? Mostre a nota e os votos, usando mais votos para desempatar. | `titulo`, `nota_imdb`, `qtd_imdb` |
| Q47 | E dessas aí, quais tiveram nota acima de 7 no IMDb? | `titulo`, `nota_imdb` |
| Q48 | Faz o mesmo pra terror. | `titulo`, `lucro_brl` |
| Q49 | Agora só de 2020 pra cá. | `titulo`, `receita_brl`, `ano_lancamento` |
| Q50 | Quem dirigiu esse filme? | Pedido de esclarecimento |

Todos os casos Q01–Q14 também registram o contrato semântico usado pelo agente: métrica,
unidade, período, população válida e limitações. Essas orientações entram no
contexto do modelo para que a resposta em português explique os filtros
aplicados e não acrescente números que não vieram da ferramenta.

O comparador em `genai/app/evaluation_runner.py` verifica quantidade de linhas
e valores, com tolerância de R$ 0,01 para números. Se as colunas tiverem os
mesmos nomes, a comparação usa esses nomes; caso o SQL equivalente use aliases
distintos, os valores são comparados na ordem retornada. O script
`genai/scripts/evaluate_agent_snapshot.py` reproduz o ciclo completo com o SQL
de referência como modelo simulado, sem rede, para validar o executor e o
comparador antes de qualquer teste manual com Gemini. Além dos valores, o
script verifica as colunas obrigatórias de cada caso.

## Cenários ampliados

Além das formulações canônicas, `genai/app/evaluation_scenarios.py` cobre
reformulações de linguagem, filtro por ano, empates, resultado vazio,
ambiguidade e perguntas sobre recursos da plataforma. Esses cenários usam
mocks e expectativas de comportamento; não fazem chamadas reais ao provedor.

## Cobertura atual

A suíte contém 50 perguntas oficiais. Os casos Q15–Q24 e Q25–Q50 estão no
[catálogo da expansão](coverage-todo.md), com SQL em
[expansion-reference-queries.sql](expansion-reference-queries.sql) e
[round-two-reference-queries.sql](round-two-reference-queries.sql).
Q47–Q49 usam contexto anterior. Q36 e Q50 avaliam pedidos de esclarecimento.
Consulte a [bateria fixa e os resultados por provedor](provider-validation.md).
