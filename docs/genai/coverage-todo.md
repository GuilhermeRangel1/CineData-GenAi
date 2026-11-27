# Expansão da cobertura do agente

Ampliar Q01–Q14 para 50 casos de avaliação em duas rodadas, de 24 e 50 casos.
Cada caso novo representa uma intenção distinta e tem um resultado conferido
no Gold. Escrever duas reformulações naturais por caso novo e reservar ao menos
uma para a avaliação. As reformulações ficam fora da contagem.

Combinar casos simples e compostos, mantendo Q01–Q14 como casos de regressão.
Um caso composto exige
mais de uma operação relevante para responder: comparar grupos ou períodos,
cruzar relações e calcular métricas, usar um agregado para selecionar os
resultados ou interpretar um seguimento no contexto da conversa. Um ranking
com vários filtros, sozinho, conta como um caso de filtros combinados.

## Rodada 1 · 24 casos

- [x] Conferir no esquema e no banco Gold quais das 10 perguntas candidatas
  têm os dados necessários e definir o recorte inicial abaixo.
- [x] Executar as referências no Gold em modo leitura. Q16 retornou zero
  linhas, um resultado esperado que a resposta precisa explicar.
- [x] Integrar Q15–Q24 ao avaliador de chamadas reais com
  `--expansion-reference`, preservando a rodada padrão de 14 casos.
- [x] Medir as 14 originais e as 10 novas antes dos ajustes desta revisão. Registrar
  modelo, SQL gerado e executado, resultado, fallback e latência. Classificar
  erros de interpretação, SQL, texto e indisponibilidade.
- [x] Corrigir os padrões que se repetem e comparar as 24 antes e depois.
  Contar como acerto direto apenas as respostas corretas geradas pelo agente
  sem correção por SQL de referência.
- [x] Criar reformulações separadas das instruções do agente e rodar uma
  por caso. Manter uma segunda formulação de Q15–Q24 reservada para próxima
  avaliação.
- [x] Confirmar pelo menos um acerto direto do Gemini com cada uma das 24
  perguntas originais e com a primeira reformulação de cada caso.
- [x] Confirmar 24 acertos diretos do Gemini em uma única execução canônica.
- [ ] Confirmar 24 acertos diretos em uma única execução coloquial. Todos
  passaram entre rodadas e retestes. A última execução parou com HTTP 429
  e o Gemini informou limite diário dos dois modelos.

A nova validação desta etapa usa Gemini. As validações anteriores de Groq
e OpenRouter ficam registradas em [resultados dos provedores](provider-validation.md).

### Primeira rodada com APIs reais

Foram tentados os 24 casos por provedor com `--model-only`, em processos
isolados e sem fallback entre provedores. O avaliador compara o resultado
tabular; a qualidade do texto final ainda precisa de revisão.

| Provedor | Acertos diretos | Bloqueios |
| --- | ---: | --- |
| Gemini | Sem resultados avaliáveis | 24 falhas de credenciais |
| Groq | 9 nas originais | 14 falhas temporárias do provedor e 1 timeout SQL (Q09) |
| OpenRouter | Sem resultados avaliáveis | 24 falhas de credenciais |

No Groq, as dez novas ficaram bloqueadas por falhas temporárias. Retomar com
as credenciais de Gemini e OpenRouter revisadas e o Groq em lotes menores.

### Nova rodada após recriar o container

Cada provedor completou as 24 tentativas isoladas, com três segundos de
intervalo. A coluna de acertos diretos conta apenas resultados com origem
`model`. O Gemini também acertou a Q04 após reparar o SQL (`model_repaired`).

| Provedor | Diretos nas 14 originais | Diretos nas 10 novas | Falhas do provedor | Erros do agente | Divergências de resultado |
| --- | ---: | ---: | ---: | ---: | ---: |
| Gemini | 6 | 3 (Q15, Q16, Q23) | 12 | 1 | 1 |
| Groq | 10 | 0 | 14 | 0 | 0 |
| OpenRouter | 9 | 2 (Q16, Q17) | 8 | 3 | 2 |

No Gemini, a API também rejeitou chamadas cujo prazo restante ficou abaixo
do mínimo de 10 segundos. A Q20 voltou vazia, embora a referência tenha um
diretor. No OpenRouter, a Q15 divergiu no ranking e a Q19 retornou o ano em
texto em vez de número. No Groq, as dez novas ficaram sem resultado
avaliável devido a falhas temporárias. A avaliação comparou linhas e valores.
A naturalidade do texto e as reformulações reservadas seguem pendentes.

### Reteste dirigido após os ajustes

O agente passou a orientar buscas de pessoas sem diferenciar maiúsculas e
minúsculas e a preferir o ano numérico do catálogo. O adaptador Gemini envia
um prazo aceito pela API e aplica localmente o tempo restante. As perguntas
de ranking agora declaram o desempate por votos quando ele faz parte da
referência, e Q18 explicita a necessidade de votos no TMDB. Para Q15–Q24,
o avaliador ignora apenas chaves técnicas extras, preservando a comparação
dos valores solicitados.

- Gemini acertou diretamente Q18, Q20 e Q24 no reteste final.
  Q19 e Q22 tiveram falhas temporárias no lote anterior.
- OpenRouter acertou diretamente Q15 e Q19 no reteste dirigido.
- Groq teve falhas temporárias nos quatro casos do lote Q15, Q16, Q17 e Q20.

Os retestes cobriram somente esses casos e não substituem a avaliação
completa por provedor.

### Cobertura acumulada após novos retestes

Na rodada posterior com os limites normais (12 segundos por tentativa e
40 por pergunta), o Gemini acertou diretamente 21/24, o Groq 4/24 e o
OpenRouter não teve resposta avaliável. No Gemini, Q06 e Q12 passaram
diretamente em retestes. Q17 passou após reparo do SQL gerado pelo modelo,
sem consulta de referência. Outro reteste de Q17 falhou no provedor antes
de produzir SQL. Ainda falta confirmar os 24 acertos diretos na mesma rodada.

- Gemini: 24 de 24 casos com ao menos um acerto direto. Q07, Q09, Q21 e Q22
  passaram em retestes com limite de 25 segundos por tentativa e orçamento
  de 60 segundos, aplicados só ao processo de avaliação. A cobertura combina
  rodadas e não representa uma única execução completa.
- Groq: 11 de 24 casos com acerto direto. A Q15 retornou HTTP 429 no
  diagnóstico da consulta. Os 13 casos ainda pendentes voltaram a apresentar
  falhas temporárias durante os lotes.
- OpenRouter: 18 de 24 casos com acerto direto. Pendentes Q07, Q12, Q18,
  Q20, Q21 e Q23. O último lote dessas seis perguntas teve falhas temporárias.

O agente agora recebe também orientações sobre os nomes dos gêneros no
catálogo, a localização das colunas financeiras e a escala dos percentuais.
O reteste da Q09 orientou o uso da coluna real de nome das pessoas. A Q21
passou após explicitar a fórmula de lucro e a ordem dos campos solicitados.

### Revisão das 24 com reformulações

As chamadas usaram um provedor por processo e `--model-only`. A referência
Gold foi usada somente para conferir os dados. O relatório por pergunta
registra o SQL proposto e o que chegou ao executor, a origem da resposta,
o modelo configurado, as rotas observadas, o texto e o tempo total. Os
registros distinguem acerto direto (`model`) de reparo (`model_repaired`).
Para reproduzir a rodada a partir da raiz de `genai`, em um ambiente com
acesso ao Gold e às credenciais do provedor:

```powershell
python -m scripts.evaluate_live_providers --model-only --providers gemini --reference ../docs/genai/reference-queries.sql --expansion-reference ../docs/genai/expansion-reference-queries.sql --interval 3 --output ./gemini-canonical.json
python -m scripts.evaluate_live_providers --model-only --providers gemini --reference ../docs/genai/reference-queries.sql --expansion-reference ../docs/genai/expansion-reference-queries.sql --interval 3 --paraphrases --output ./gemini-paraphrases.json
```

Na primeira rodada canônica, o Gemini acertou diretamente 23/24. A Q14
excedeu o prazo de execução do SQL. O Groq acertou diretamente 11/24,
teve 12 falhas temporárias e um erro de SQL (Q14). O OpenRouter teve 24
falhas temporárias. Os retestes de Groq e OpenRouter registraram HTTP 429.

Um reteste posterior do Groq confirmou Q01 e Q14 diretamente. A Q09
gerou SQL em 1,64 s, mas o executor interrompeu a consulta no prazo de
15 s. Q20 e Q23 ficaram sem SQL avaliável. O diagnóstico de Q20 confirmou
HTTP 429 pelo limite diário de tokens do modelo: 199.889 de 200.000
usados, com 3.764 tokens solicitados na tentativa.

O executor passou a reconhecer a agregação de duplas pela estrutura da
consulta, mesmo quando o modelo escolhe nomes diferentes para as CTEs.
Com o ajuste, o SQL já gerado pelo Groq para Q09 foi reexecutado sem
alterações e bateu com o Gold em 9,09 s. Essa reprodução não conta como
uma nova chamada nem confirma um novo acerto direto. A verificação com
as 24 referências confirmou que somente Q09 recebe o prazo específico de
duplas. Após a janela de nova tentativa indicada pelo Groq, Q09, Q14,
Q20 e Q23 ainda receberam HTTP 429 antes de gerar SQL.

Na rodada seguinte, o Groq acertou Q09 diretamente em 17,58 s, incluindo
geração e execução. Q14, Q20 e Q23 voltaram a receber HTTP 429 nesse lote.

O lote seguinte com as 11 pendências canônicas de `openai/gpt-oss-20b`
recebeu HTTP 429 em todos os casos. Para Q15, a API confirmou o limite
diário: 199.393 de 200.000 tokens usados e 3.356 solicitados.
O avaliador passou a aceitar `--stop-on-rate-limit`, que salva o progresso,
registra o prazo informado pelo provedor e encerra no primeiro HTTP 429.

Ao reexecutar o SQL que o Groq gerou para a reformulação da Q05, as dez
linhas bateram com o Gold após reconhecer os aliases e alinhar as
colunas. Esse caso tinha sido marcado como divergente antes desse
ajuste de comparação.

O Groq também foi avaliado com `openai/gpt-oss-120b`, definido apenas
no processo de teste. O modelo obteve acerto direto em cada uma das
24 perguntas canônicas em lotes somados com a mesma versão final do
agente, sem SQL de referência. Houve
pausas entre chamadas para respeitar HTTP 429 de curta duração.
A Q08 passou após explicitar no prompt que o executor exige JOIN com
ON ou USING. Q11 e Q12 passaram sem reparo após orientar o uso de
DENSE_RANK para preservar empates. Na Q18, o comparador passou a
reconhecer o alias `diff` e a comparar as métricas pelos nomes.
Esse resultado é do 120B. O 20B continua com casos sem resultado
avaliável pelo limite diário.

O reteste do OpenRouter recebeu HTTP 429 antes de produzir SQL em Q01,
Q05, Q20 e Q24. Uma chamada curta confirmou o limite diário
`free-models-per-day`, com 0 de 50 chamadas restantes e horário de
reinício informado pela API. As quatro perguntas seguem sem uma
resposta do modelo para comparar com o Gold.

Após a renovação da cota, o OpenRouter com
`nvidia/nemotron-3.5-lightning:free` voltou a responder. Das seis
pendências históricas, Q18 e Q21 passaram diretamente. Q07 comparou
anos civis em vez da janela móvel de cinco anos, Q12 usou uma coluna
ausente na CTE e Q20 retornou apenas o cadastro do ator. Q23 esgotou
os 12 segundos de inferência. O lote não confirmou as 24 na versão atual.

Na rodada canônica completa seguinte, o mesmo modelo concluiu 24
tentativas sem HTTP 429 e obteve 18 acertos diretos. Q02, Q07 e Q20
divergiram do resultado esperado. Q09, Q11 e Q23 esgotaram o prazo
de 12 segundos de inferência antes de gerar SQL.

Nos retestes dos seis casos, Q02, Q07, Q09, Q11 e Q20 passaram
diretamente. O agente explicita a ordenação do lucro médio, usa as datas
da janela móvel e pede a consulta completa para colaborações. Para
colaborações e medianas de produtoras, usa um esquema e instruções menores
quando a pergunta se limita a esse assunto. O prazo analítico do OpenRouter
é configurável, com padrão de 36 s e teto pelo orçamento restante da pergunta
(40 s no total por padrão). Q23 passou em 35,28 s com 36 s disponíveis,
mas outro reteste no mesmo prazo expirou antes de gerar SQL. O resultado
combina rodadas e não confirma 24/24 em uma rodada final única.

As reformulações expuseram, entre outros problemas, uma comparação de
notas roteada para busca por sinopse (Q05), confusão entre lucro e margem
(Q03) e ausência de contexto na resposta vazia da Q16. O agente ganhou
regras reutilizáveis para esses casos e para a consulta de divergência da
Q14. O avaliador preserva a comparação dos valores solicitados e permite
que uma reformulação omita IDs internos ou use aliases conhecidos.

Nos retestes, Q14 passou com uma única agregação para obter a divergência
máxima. Q23 passou depois que a regra de mediana passou a exigir uma
linha por par filme e produtora, evitando multiplicar o lucro dos filmes
com coprodutoras. O Gemini acertou diretamente as 24 originais e uma
reformulação por caso, em rodadas somadas. A primeira rodada de
reformulações deu 9/24 diretos com o comparador anterior, que também
marcava como erro diferenças de IDs e nomes de colunas. Os resultados
dessas duas etapas medem critérios diferentes.

Na rodada canônica completa com a versão final, o Gemini obteve 23/24
acertos diretos. A única falha foi HTTP 503 na Q23, antes de gerar SQL.
A mesma versão acertou Q23 diretamente no reteste isolado.

A revisão de texto confirmou que a Q16 precisa dizer que nenhum ano
atendeu à comparação, com o período e os gêneros. Onde há linhas, o texto
padrão ainda encaminha para a tabela. A rodada mede o texto do serviço
analítico com os insights opcionais desativados, então não valida a
naturalidade desses insights na interface.

### Triagem inicial das 10 perguntas

A triagem usa o inventário em [gold-schema.md](gold-schema.md) e consultas
somente leitura no Gold local. Há 95.645 filmes com anos de 2016 a 2029.
Os gêneros estão em inglês no banco e Leonardo DiCaprio aparece como
`Leonardo Dicaprio`, com 12 créditos de atuação. O idioma original está nulo
em todos os filmes. A validação completa dos resultados segue pendente.

| Caso | Recorte para avaliação | Regra a conferir |
| --- | --- | --- |
| Q15 | Top 10 IMDb de documentários lançados de 2016 a 2024, com pelo menos 1.000 votos | Usar gênero, nota e votos IMDb. Manter “filmes brasileiros” e “filmes em português” como cenários separados de limitação. |
| Q16 | Lançamentos anuais de terror e comédia, 2016–2024 | Contar filmes por gênero. Um filme com os dois gêneros entra em ambos. |
| Q17 | Top 5 por lucro com orçamento de até R$ 10 milhões | Exigir orçamento e receita válidos, em BRL, e calcular receita menos orçamento. |
| Q18 | Top 5 IMDb com TMDB pelo menos um ponto abaixo e 5.000 votos IMDb | Exigir notas válidas nas duas fontes e apresentar a diferença. |
| Q19 | Ano de maior média IMDb em animação, 2016–2024 | Exigir dez filmes com avaliação válida por ano e calcular média simples. |
| Q20 | Diretores que fizeram ao menos dois filmes com Leonardo DiCaprio | Contar filmes distintos por diretor e calcular a média somente das notas IMDb válidas. |
| Q21 | Top 3 gêneros por lucro médio, 2016–2024 | Mostrar quantos filmes com orçamento e receita válidos entraram em cada média. |
| Q22 | Percentual de filmes lucrativos de ficção científica, 2016–2024 | Usar filmes com orçamento e receita válidos como denominador e lucro positivo no numerador. |
| Q23 | Top 5 produtoras por percentual de filmes lucrativos | Exigir dez filmes distintos elegíveis por produtora e mostrar numerador e denominador. |
| Q24 | Top 10 por lucro entre filmes com IMDb ≥ 8, 10 mil votos e receita superior ao dobro do orçamento, desde 2016 | Usar valores comparáveis em BRL e orçamento positivo. |

### Exemplos compostos para a primeira rodada

- **Q16:** “De 2016 a 2024, em quais anos saíram mais filmes de terror do que
  de comédia? Quanto foi a diferença em cada um desses anos?”
- **Q20:** “Dos diretores que trabalharam com Leonardo DiCaprio pelo menos
  duas vezes, quais tiveram a melhor nota média no IMDb nesses filmes? Mostre
  quantos filmes fizeram juntos e quantos entraram na média.”
- **Q21:** “Quais três gêneros tiveram o maior lucro médio entre 2016 e 2024?
  Para esses mesmos gêneros, qual percentual dos filmes deu lucro e quantos
  filmes entraram nas contas?”
- **Q23:** “Entre as produtoras com pelo menos dez filmes com dados
  financeiros, quais têm a maior proporção de filmes lucrativos? Mostre o
  total de filmes, quantos deram lucro e o lucro mediano de cada produtora.”

A referência de cada caso composto precisa conferir todas as partes do
pedido. Registrar acertos parciais para diagnóstico e contar acerto direto
apenas quando o resultado completo estiver correto.

## Rodada 2 · 50 casos

### Divisão dos 26 casos novos

- [x] **Q25–Q37 · Datas e finanças.** Cobrir “ano passado”, “de 2016 pra cá”,
  “nos últimos cinco anos”, “se pagou” e “deu prejuízo”. Exemplo composto:
  “Quais filmes de terror se pagaram no ano passado e quais tiveram a maior
  margem?”
  - **Q25 · Concentração de bilheteria.** “Que porcentagem da bilheteria
    total de 2023 veio dos dez filmes que mais arrecadaram naquele ano?”
- [x] **Q38–Q50 · Créditos, comparações e seguimentos.** Cobrir elenco,
  direção e produtoras. Depois de listar as comédias mais lucrativas, o
  seguimento “E dessas aí, quais tiveram nota acima de 7 no IMDb?” deve
  preservar o recorte anterior e acrescentar o filtro de nota.
  - **Q42 · Coproduções.** “Quais produtoras fizeram mais coproduções em
    2024? Mostre quantos filmes cada uma fez com pelo menos outra
    produtora.” Contar cada filme uma vez por produtora.

### Perguntas candidatas e critérios

Conferir cada resultado esperado no Gold antes de fechar a lista. As versões
parciais de Q21 e Q23 ficam nos testes complementares.

| Caso | Pergunta | O que conferir |
| --- | --- | --- |
| Q25 | Que porcentagem da bilheteria total de 2023 veio dos dez filmes que mais arrecadaram naquele ano? | Dividir a receita dos dez primeiros pela receita total do mesmo recorte. |
| Q26 | Quais filmes tiveram os cinco maiores prejuízos de 2023? | Usar receita e orçamento em reais e ordenar pelo maior prejuízo absoluto. |
| Q27 | Quais filmes de animação que saíram no ano passado pelo menos se pagaram? | Usar o ano civil anterior e incluir receita igual ao orçamento. |
| Q28 | Quais filmes de ação que já estrearam este ano têm orçamento e bilheteria informados? | Usar o ano corrente até a data de referência, inclusive. |
| Q29 | Dos cinco filmes mais caros de 2023, quais deram prejuízo e quanto faltou para se pagarem? | Selecionar os cinco de maior orçamento antes de filtrar pelo prejuízo. |
| Q30 | Qual foi o orçamento mediano dos filmes de terror de 2024? | Calcular a mediana dos orçamentos conhecidos, inclusive quando houver dois valores centrais. |
| Q31 | Em quais anos a comédia teve mais estreias, mas o terror teve maior lucro médio? Conte todas as estreias, mesmo sem dados financeiros, e mostre as contagens e as médias dos dois gêneros. | Cruzar as duas comparações anuais. Contar todas as estreias e só exigir dados financeiros para calcular as médias. |
| Q32 | Qual gênero mais aumentou a bilheteria total de 2022 para 2023, em reais? | Comparar as somas anuais por gênero e selecionar o maior aumento. |
| Q33 | Quais filmes de 2023 ficaram no top 10 tanto em bilheteria quanto em lucro? | Montar os dois rankings e devolver a interseção. |
| Q34 | Em 2024, qual gênero teve a maior proporção de filmes com orçamento e bilheteria informados? Qual foi a porcentagem? | Dividir o total com os dois dados pelo total de filmes do gênero. |
| Q35 | Quanto as animações de 2023 arrecadaram para cada real de orçamento, somando tudo? | Dividir a receita total pelo orçamento total sobre o mesmo conjunto de filmes. |
| Q36 | Quais filmes bombaram no ano passado? | Pedir esclarecimento ou declarar se usou bilheteria, popularidade ou outro critério. |
| Q37 | Quantos filmes estrearam nos últimos cinco anos em cada gênero? | Usar a janela móvel e contar cada filme uma vez por gênero. |
| Q38 | Quem está no elenco de *Barbie*, de 2023? | Identificar o filme no catálogo e listar seus créditos de atuação. |
| Q39 | Em que filmes Leonardo DiCaprio atuou sob direção de Martin Scorsese? Mostre o título e o ano de cada um. | Cruzar atuação e direção e listar os filmes em comum. |
| Q40 | Quais cinco duplas de atores fizeram mais filmes de terror juntas em 2023? | Contar os filmes sem duplicar A–B e B–A. Ordenar os nomes dentro de cada dupla antes do desempate. |
| Q41 | Quais diretores dirigiram pelo menos um filme de terror e um de comédia desde 2016? Mostre até dez nomes em ordem alfabética. | Verificar os dois gêneros na filmografia e aplicar o limite de datas. |
| Q42 | Quais produtoras fizeram mais coproduções em 2024? Mostre quantos filmes cada uma fez com pelo menos outra produtora. | Identificar filmes com mais de uma produtora e contar cada filme uma vez por produtora. |
| Q43 | Das cinco produtoras com mais filmes de 2023, qual foi o filme de maior bilheteria de cada uma naquele ano? | Escolher as produtoras antes de selecionar um filme por produtora. Mostrar a receita em reais. |
| Q44 | Qual produtora trabalhou com o maior número de diretores diferentes em 2024? | Cruzar créditos de produção e direção e contar pessoas distintas. |
| Q45 | Quais filmes de 2019 têm nota 8 ou mais e pelo menos 10 mil votos tanto no IMDb quanto no TMDB? | Aplicar os dois critérios separadamente em cada fonte. |
| Q46 | Quais filmes saem do top 10 por nota no IMDb quando o mínimo sobe de mil para 10 mil votos? | Montar os dois rankings e mostrar os títulos presentes só no primeiro. |
| Q47 | Depois de listar as comédias mais lucrativas: “E dessas aí, quais tiveram nota acima de 7 no IMDb?” | Filtrar os filmes já exibidos preservando o recorte anterior. |
| Q48 | Depois de listar as comédias mais lucrativas: “Faz o mesmo pra terror.” | Trocar o gênero e preservar a métrica, o período e o tamanho da lista. |
| Q49 | Depois de listar as animações de maior bilheteria: “Agora só de 2020 pra cá.” | Alterar o período e refazer o ranking com o gênero e a métrica anteriores. |
| Q50 | Sem mencionar um título antes: “Quem dirigiu esse filme?” | Pedir o título quando não houver contexto suficiente para identificar o filme. |

### Tarefas da rodada

- [x] Dar ao agente um catálogo de métricas, fontes de nota, chaves, relações e
  limites do Gold. Documentar nulidade e como evitar contagens duplicadas.
  Ver [regras das métricas](metric-rules.md) e [esquema do Gold](gold-schema.md).
- [x] Adicionar 26 casos inéditos com filtros combinados, múltiplas métricas,
  comparações por período e cruzamentos de créditos.
- [x] Encurtar as sugestões de Q15–Q24 na Ajuda e manter as versões completas
  na avaliação. Incluir as versões parciais de Q21 (ranking por lucro médio)
  e Q23 (ranking por percentual lucrativo) na Ajuda e em testes complementares
  com resultados esperados próprios no Gold, fora dos 50 casos principais.
- [x] Avaliar versões curtas e naturais dos 24 casos da primeira rodada.
  Quando a frase pedir os mesmos dados, manter a referência do caso original
  e contar a frase como reformulação, fora dos 50 casos principais.
- [x] Avaliar reformulações coloquiais, ambiguidades e seguimentos que
  preservem os filtros anteriores.
- [x] Melhorar a escrita em português e avaliar separadamente a fidelidade aos
  dados e a clareza da resposta.

### Primeiro teste com o Gemini

- [x] Integrar os 12 casos tabulares de Q25–Q37 ao avaliador e conferir suas
  referências no Gold, em modo somente leitura.
- [x] Rodar esses casos com o Gemini isolado em modo `--model-only`.
- [x] Integrar Q36 e Q38–Q50. Q36 e Q47–Q50 precisam avaliar esclarecimento
  ou contexto da conversa além dos resultados de SQL.
- [x] Retestar os rankings Q29 e Q33 e definir como o comparador trata
  aliases e informações complementares sem perder a validação das métricas.

Foram confirmados seis acertos diretos: Q26, Q27, Q28, Q30, Q35 e Q37.
Q35 expirou no lote e passou no reteste isolado. Q25 passou após reparo
do SQL pelo próprio modelo. Q27 e Q28 retornaram listas vazias, como
esperado no Gold na data da execução. Os recortes financeiros de Q25,
Q26, Q29, Q33 e Q35 foram ajustados para 2023 e Q32 compara 2022 com
2023, devido à escassez de dados em 2024.

Q29 filtrou os prejuízos antes de escolher os cinco maiores orçamentos.
Q33 excluiu filmes sem orçamento do ranking de bilheteria. Q31 e Q32
coincidiram com a referência nas métricas solicitadas, mas falharam no
comparador por diferenças nas colunas. Q34 identificou o gênero correto
e omitiu o percentual previsto na referência.

Após os ajustes, o Gemini acertou 11 dos 12 casos diretamente na nova
rodada. Q31 passou em reteste isolado após reparo do SQL pelo modelo. O
caso agora pede e valida as contagens e as médias dos dois gêneros. A
correção separa a população de estreias da população com dados financeiros.

Na auditoria posterior, o Gemini incluiu um filme sem receita na
lista de prejuízos da Q29. O prompt agora exige receita conhecida para
classificar prejuízo. Q31 recebeu aliases para as contagens e Q34 passou
a usar `percentual_informado` para identificar a métrica de cobertura.
Os três casos passaram no reteste. A reexecução somente leitura
comparou as colunas por nomes e aliases explícitos, sem recorrer à
posição: os valores pedidos e o número de linhas coincidiram nos 12
casos, juntando o lote e os retestes. Q34 passou após reparo.
O texto foi conferido no serviço, sem renderização no navegador.

Na rodada seguinte, Q25 esbarrou na autorização do SQLite ao repetir no
`FROM` externo uma CTE já lida por subconsultas. O prompt orienta uma
única leitura externa dos totais. A janela móvel de Q37 também foi
explicitada, e Q31 passou a pedir que estreias sem dados financeiros
entrem nas contagens. A rodada completa após esses ajustes obteve
12/12 acertos diretos com o Gemini, sem reparos nem consulta de referência
como resposta.

### Segundo lote e conferência da rodada completa

- [x] Conferir no Gold as referências de Q38–Q49 e cadastrar Q36 e Q50
  como casos de esclarecimento.
- [x] Avaliar Q47–Q49 com a pergunta anterior no contexto e conferir o
  resultado de cada seguimento com o Gold.
- [x] Obter pelo menos um resultado esperado em cada caso de Q25–Q50
  com chamadas reais ao Gemini.
- [x] Completar Q25–Q50 em uma única execução sem bloqueio de cota.
  Com Gemini, 24 consultas bateram com a Gold direto e Q36/Q50 esclareceram.

No segundo lote, 12 respostas tabulares bateram com o Gold e Q36 e Q50
pediram os esclarecimentos esperados. Q40 foi delimitada a terror em
2023 para reduzir o custo do cruzamento de créditos. Q43 passou a usar
2023 tanto na seleção das produtoras quanto na seleção dos filmes, após
o recorte de todo o catálogo exceder o prazo do executor. Q38 usa
Barbie, presente no catálogo, e Q45 usa 2019, com resultados nos dois
critérios de nota e votos.

A execução conjunta de Q25–Q50 parou em Q39 por HTTP 429. A sequência
foi retomada a partir de Q39. O caso passou no reteste depois que a
pergunta explicitou que também pede o ano. Q31 devolveu os valores
corretos com aliases diferentes para as médias e passou após o ajuste
no comparador. A cobertura de 26/26 combina as execuções e inclui
dois pedidos de esclarecimento e resultados obtidos após reparo do SQL.
As consultas de referência serviram somente para comparação.

Na verificação posterior com o Gemini, 21 dos 24 casos tabulares
retornaram resultados que bateram com o Gold, incluindo Q41 no reteste.
As consultas executadas foram reproduzidas em modo somente leitura e
as métricas foram comparadas pelo nome da coluna ou por alias explícito.
Q36 pediu o esclarecimento esperado. Q40, Q46, Q48 e Q50 ficaram sem
nova resposta avaliável por timeout ou HTTP 503. O reteste foi
interrompido pelo HTTP 429. Os quatro já haviam passado em execuções
anteriores.

Para reproduzir apenas o primeiro lote a partir de `genai`:

```powershell
python -m scripts.evaluate_live_providers --providers gemini --model-only --reference ../docs/genai/reference-queries.sql --round-two-reference ../docs/genai/round-two-reference-queries.sql --cases Q25,Q26,Q27,Q28,Q29,Q30,Q31,Q32,Q33,Q34,Q35,Q37 --interval 2 --stop-on-rate-limit
```

### Respostas em linguagem natural e perguntas de investigação

- [x] Mostrar uma resposta curta acima da tabela ou gráfico. Começar por
  resultados de uma linha e listas de filmes, gêneros, produtoras ou pessoas,
  usando os valores da consulta.
- [x] Revisar os insights de Q15–Q50 com os resultados de referência da
  Gold. Conferir separadamente os esclarecimentos de Q36 e Q50.
  A [revisão por pergunta](insights-review.md) registra o resultado.
- [x] Gerar insights a partir de comparações por ano, empates, diferenças
  entre resultados, rentabilidade e retorno por real de orçamento.
- [x] Criar o primeiro caso de investigação sobre o que contribuiu para uma
  mudança no Gold, começando pela alta de bilheteria entre dois anos.
  Comparar volume de lançamentos, receita média e concentração por filme.
- [x] Conferir a primeira investigação com a Gold e informar que a
  comparação mede contribuições observadas, sem identificar causas externas.
- [x] Dar contexto ao empate de produtoras na Q23 mostrando o tamanho de
  cada amostra quando a consulta retorna essa contagem.
- [x] Repetir as Q15–Q50 pelo fluxo da API do chat usando as frases da Ajuda
  e os exemplos de continuação mantidos no avaliador.
  Comparar primeiro as linhas retornadas com a Gold e depois conferir se o
  insight continua correto com as colunas efetivamente retornadas.
- [x] Priorizar casos com uma linha, resultado vazio ou colunas reduzidas.
  Acrescentar contexto com outra consulta ao Gold quando isso ajudar a
  responder à pergunta.
- [x] Acrescentar investigações sobre lucro total e nota média no IMDb.
  Conferir as agregações de 2022 e 2023 com consultas independentes em
  modo leitura na Gold. As respostas mostram cobertura e composição.

#### Reteste de regressão

- [x] Revalidar as três investigações pela API local e a seleção da métrica
  dos gráficos no front. O texto abre com a comparação pertinente.
- [x] Na pergunta sobre queda do lucro e aumento da proporção de filmes
  lucrativos, pedir os dois anos quando não há comparação anterior. Reusar
  o período de uma comparação anterior de lucro do catálogo na conversa.
- [ ] Completar uma nova execução das perguntas canônicas, reformulações e
  exemplos da Ajuda com Gemini. A chave atualizada respondeu à Q01, mas o
  reteste esbarrou no limite diário por projeto e modelo do Gemini gratuito.
- [ ] Completar o reteste dos provedores alternativos. Groq confirmou Q01–Q06
  e retornou 429 na Q07. OpenRouter confirmou 28 casos, incluindo Q09 após
  ajustar a orientação da consulta. Q23 e Q30 ficaram pendentes por 429,
  e Q31–Q50 ficaram fora da execução atual.

Em 23/11/2026, o Groq confirmou Q07–Q24 contra a Gold em várias execuções.
Q25 retornou 429 nas quatro tentativas de retomada, mesmo respeitando o
intervalo informado nas respostas. O OpenRouter confirmou 20 dos 22 casos
pendentes, incluindo Q23 e Q30. Faltam Q48 e Q49, que ficaram sem resposta
avaliável nas repetições. As correções validadas nessa rodada abrangem o
recorte de avaliações válidas da Q19, os créditos da Q20 e Q39, a mediana
da Q23, a base financeira da Q35, o desempate da Q42 e o seguimento da Q47.

Considerando as chamadas reais de 23/11 em conjunto, as 50 perguntas
canônicas passaram em pelo menos um provedor, incluindo os esclarecimentos
esperados de Q36 e Q50. A Q25 passou no OpenRouter após padronizar a
porcentagem na escala de 0 a 100. O Gemini confirmou 29 das 49 canônicas
selecionadas (Q02–Q50). No reteste dirigido das reformulações pela API,
confirmou Q20, Q35 e Q39. As demais reformulações continuam pendentes.
Os resultados combinados não certificam a bateria completa por provedor.

Na retomada, o Gemini confirmou mais seis canônicas (Q03, Q07, Q09,
Q10, Q12 e Q14), chegando a 35 das 49 selecionadas desde Q02. Houve
novos HTTP 429 e timeouts antes de completar o restante e as reformulações.
O OpenRouter confirmou Q49 após a correção de rota das continuações.
Q48 usa a rota analítica no teste local, mas voltou a receber HTTP 429
na chamada real. Pela API, o novo reteste confirmou as reformulações
Q01, Q03 e Q04 no Gemini e Q19, Q23, Q25 e Q35 no OpenRouter.

O Groq confirmou mais 14 canônicas: Q25–Q28, Q30–Q32, Q35–Q37 e Q39–Q42.
Faltam Q29, Q33, Q34, Q38 e Q43–Q50 nessa retomada. As orientações de
SQL para população do ranking, período e créditos foram ajustadas. Os
últimos retestes isolados voltaram a receber 429 em Q19 no Gemini, Q29 no
Groq e Q48 no OpenRouter. Os 203 testes locais passaram, incluindo os dois
novos casos de roteamento para continuações curtas.

No reteste seguinte, o Groq confirmou Q29, Q33, Q34 e Q38. Em Q33, cada
ranking passou a ter seus próprios filtros financeiros. Em Q34, a
proporção foi calculada sobre os filmes do ano pedido. Q43 ainda apresentou
SQL inválido no Groq. O OpenRouter voltou a retornar 429 na Q48 e na
primeira reformulação da API. O Gemini aprovou oito reformulações na nova
execução pela API antes de um 429 na Q13. Esses resultados não encerram a
validação individual de todas as perguntas e reformulações.

O Groq também confirmou Q44–Q46. Somando os retestes canônicos desta
expansão, ficaram pendentes Q43 e Q47–Q50 no Groq. A Q47 retornou 429
na tentativa de reparo. A retomada das reformulações voltou a receber
429, com uma reformulação confirmada no Groq nesta rodada.

### Períodos na fala cotidiana

- [x] Reconhecer também “ano anterior”, “esse ano” e “de 5 anos pra cá”.
  Conferir os limites em 31/12/2025 e 01/01/2026, e validar reformulações
  de Q27 e Q37 com Gemini sem fallback de referência, incluindo os insights.

- [x] Interpretar “desde 2016” e “de 2016 pra cá” a partir de 1º de janeiro
  de 2016 até a data atual, inclusive, para perguntas sobre filmes já lançados.
  Usar a data de referência da execução. Pedidos explícitos sobre lançamentos
  futuros podem incluir datas posteriores, de acordo com o recorte solicitado.
- [x] Cobrir “esse ano”, “ano passado” e “nos últimos cinco anos”. Distinguir
  o ano civil anterior de uma janela móvel e usar datas de referência fixas
  na avaliação, incluindo a virada do ano e os limites inclusivos.
- [x] Avaliar essas expressões em rankings, comparações e perguntas compostas,
  com reformulações reservadas. Em seguimentos como “agora só de 2020 pra cá”,
  atualizar o período e preservar os demais filtros da pergunta anterior.

### Vocabulário de cinema e fala coloquial

- [x] Orientar a consulta a distinguir “se pagou” de “deu lucro” e
  registrar “sci-fi” como sinônimo de ficção científica no agente e
  nas [regras das métricas](metric-rules.md).

- [x] Cobrir termos comuns em português e empréstimos usados no dia a dia:
  “bilheteria”, “arrecadou”, “custou pra fazer”, “deu prejuízo”, “se pagou”,
  “estreou”, “elenco”, “quem dirigiu”, “animação” e “sci-fi”. Relacionar cada
  expressão aos dados disponíveis e explicar o que o catálogo permite medir.
- [x] Avaliar frases como “quais bombaram de bilheteria de 2016 pra cá?”,
  “quais floparam mesmo custando caro?” e “quem tá no elenco e quem dirigiu?”.
  Quando “bombou”, “flopou” ou “mais bem avaliado” admitir métricas que mudam
  a resposta, pedir esclarecimento ou explicitar o critério usado.
- [x] Reservar reformulações com frases curtas, ordem diferente dos pedidos,
  abreviações e erros comuns de digitação. Conferir que o agente preserva
  entidades, filtros e métricas em perguntas simples, compostas e seguimentos
  como “e desses aí, quais se pagaram?”.
- [x] Usar as frases como casos de avaliação. Ensinar conceitos e relações
  reutilizáveis ao agente e medir a generalização com frases reservadas.

### Atualização de retestes em 23/11/2026

O Groq passou Q43 e Q47 em chamadas isoladas, com SQL gerado pelo modelo e
resultados conferidos contra a Gold. Para Q43, a orientação passou a limitar
os filmes às cinco produtoras antes do ranking de bilheteria. Para Q47, o
reparo de SQL agora inclui o detalhe do erro do SQLite e reforça os nomes
reais das colunas. Q48–Q50 já haviam passado no Groq; Q47 também passou no
Gemini e no OpenRouter nesta data. O OpenRouter continuou sem resposta
avaliável para Q48 por HTTP 429.

Assim, todas as perguntas canônicas Q01–Q50 têm ao menos um acerto direto
registrado em algum provedor, somando as execuções. Isso não equivale a uma
execução completa por provedor: a bateria inteira ainda não foi repetida sem
limites e várias reformulações continuam pendentes. O teste local mais recente
passou com 204 testes, e o Ruff passou nos arquivos alterados.

### Reteste da Q48 em 27/11/2026

O OpenRouter passou a Q48 em uma chamada real isolada, em 17,4 s.
Ao receber “Faz o mesmo pra terror”, manteve o ano de 2023, o ranking
por lucro e o limite de cinco filmes. Os cinco resultados do SQL gerado
pelo modelo bateram com a Gold. Groq e OpenRouter agora têm cobertura
das 50 perguntas canônicas somando as execuções e os retestes.
As reformulações por provedor continuam pendentes.

A ordem ativa no Docker foi confirmada como Gemini → Groq → OpenRouter.
Os 46 testes do roteador e dos adaptadores passaram, incluindo os
cenários de fallback com falhas simuladas.
