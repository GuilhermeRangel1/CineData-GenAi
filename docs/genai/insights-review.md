# Revisão dos insights de Q15 a Q50

As 34 consultas de referência foram executadas na Gold e suas linhas foram usadas como entrada para a mesma função que calcula os insights no chatbot. Q36 e Q50 foram chamadas pelo agente e devem pedir esclarecimento. Esta revisão verifica a interpretação dos dados de referência. A geração de SQL pelos provedores tem uma avaliação própria.

| Caso | Linhas na Gold ou comportamento | Observação revisada |
| --- | --- | --- |
| Q15 | 10 | Entre os resultados exibidos, The Grand Tour: Survival Of The Fattest lidera em nota no IMDb e supera Nathan For You: Finding Frances em 0,1. |
| Q16 | 0 | Nenhum ano do recorte apresentou a superioridade pedida. Anos empatados ficam de fora da comparação estrita. |
| Q17 | 5 | Entre os resultados exibidos, Dragon Ball Super: Broly lidera em lucro e supera Secret Superstar em R$ 49.578.926,21. |
| Q18 | 5 | A maior diferença entre IMDb e TMDB nos títulos exibidos foi de 4,8 pontos, em The Silence Of Swastika. |
| Q19 | 1 | A média desse ano se apoia em 272 títulos avaliados. Cada título tem o mesmo peso na média. |
| Q20 | 1 | A média do IMDb considera 2 dos 2 filmes em comum (100% dos títulos). |
| Q21 | 3 | Entre os resultados exibidos, Science Fiction lidera em lucro médio e supera Adventure em R$ 31.317.159,70. |
| Q22 | 1 | Dos 134 filmes com os dois valores registrados, 46 não tiveram lucro positivo. |
| Q23 | 5 | Marvel Studios e Vertigo Entertainment empataram com 100% de filmes lucrativos. A porcentagem considera 17 filmes da primeira e 11 da segunda. |
| Q24 | 10 | Entre os resultados exibidos, Spider-man: No Way Home lidera em lucro e supera Avengers: Endgame em R$ 151.257.282,74. |
| Q25 | 1 | 50,35% da receita registrada ficou fora dos dez maiores. |
| Q26 | 5 | Entre os resultados exibidos, Lost In The Stars lidera em prejuízo e supera Haunted Mansion em R$ 82.097.083,52. |
| Q27 | 0 | A lista vazia indica que nenhum filme com os valores necessários entrou no resultado. Filmes sem bilheteria ou orçamento informado não podem ser classificados pelo ponto de equilíbrio. |
| Q28 | 0 | Nenhum lançamento de ação do recorte tem orçamento e bilheteria registrados juntos. A ausência dos dois dados impede comparar os valores. |
| Q29 | 2 | Entre os resultados exibidos, Lost In The Stars lidera em prejuízo e supera The Flash em R$ 245.011.595,28. Só esse título responde por 72,2% do total de prejuízo entre as 2 linhas exibidas. |
| Q30 | 1 | Pelo menos metade dos filmes com orçamento informado custou até R$ 10.230,20. A mediana reduz a influência das produções mais caras. |
| Q31 | 3 | Em 2018, a vantagem do terror no lucro médio foi a maior entre os anos exibidos (R$ 82.834.390,32), mesmo com 1084 estreias a menos. |
| Q32 | 1 | Em History, a bilheteria registrada foi de R$ 2.706.820.580,83 em 2022 (16 filmes com dados) e R$ 9.621.360.416,41 em 2023 (11 filmes com dados). Isso equivale a uma alta de 255,45%. |
| Q33 | 8 | Os dois rankings têm 8 títulos em comum. Isso corresponde a 80% das vagas de cada top 10. |
| Q34 | 1 | 97,73% dos filmes do gênero não têm os dois valores registrados. |
| Q35 | 1 | Para cada real de orçamento, a bilheteria informada ficou R$ 3,39 acima do valor gasto. |
| Q36 | Esclarecimento | Você quer medir o sucesso pela bilheteria, pela popularidade ou pelas notas? |
| Q37 | 19 | Entre os resultados exibidos, Drama lidera em número de filmes e supera Comedy em 2.573. |
| Q38 | 10 | O catálogo registra 10 nomes no resultado. A lista reúne créditos de atuação e não estabelece quem protagonizou o filme. |
| Q39 | 1 | A lista reflete os créditos registrados no catálogo. Uma única colaboração encontrada indica a cobertura desse cruzamento, sem estabelecer o total da parceria fora do CineData. |
| Q40 | 5 | 5 resultados empatam no maior valor de número de filmes da lista (25). |
| Q41 | 10 | A lista mostra diretores com créditos nos dois gêneros. A ordem alfabética não indica quem dirigiu mais filmes. |
| Q42 | 5 | Paramount e Zdf empatam no maior valor de total de coproduções da lista (7). |
| Q43 | 5 | Das cinco produtoras selecionadas, somente Arte e ZDF têm filme com bilheteria registrada no recorte. As outras três permanecem na tabela, com bilheteria ausente. |
| Q44 | 1 | A contagem é de diretores distintos. Um diretor com vários filmes da mesma produtora entra uma única vez. |
| Q45 | 3 | A maior diferença entre IMDb e TMDB nos títulos exibidos foi de 0,14 pontos, em Avengers: Endgame. |
| Q46 | 8 | 8 dos 8 títulos que saíram do ranking tinham menos de 10.000 votos. Esses títulos ficam inelegíveis pelo novo corte, independentemente da nota. |
| Q47 | 2 | Teenage Mutant Ninja Turtles: Mutant Mayhem e Dungeons & Dragons: Honor Among Thieves empatam no maior valor de nota no IMDb da lista (7,2). |
| Q48 | 5 | Entre os resultados exibidos, Meg 2: The Trench lidera em lucro e supera Insidious: The Red Door em R$ 402.557.864,60. |
| Q49 | 5 | Entre os resultados exibidos, The Super Mario Bros. Movie lidera em bilheteria e supera Minions: The Rise Of Gru em R$ 1.927.728.848,00. |
| Q50 | Esclarecimento | Para responder a quem dirigiu o filme, preciso saber qual filme você está se referindo. Poderia especificar o título do filme? |
