# Expansão da cobertura do agente

Ampliar Q01–Q14 para 100 casos de avaliação, em três rodadas: 24, 50 e 100.
Cada caso novo representa uma intenção distinta e tem um resultado conferido
no Gold. Escrever duas reformulações naturais por caso novo e reservar ao menos
uma para a avaliação. As reformulações ficam fora da contagem.

Dividir os 86 casos novos em 43 compostos e 43 simples, mantendo Q01–Q14
como casos de regressão. Um caso composto exige
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
- [ ] Medir as 14 originais e as 10 novas antes de alterar o agente. Registrar
  modelo, SQL gerado e executado, resultado, fallback e latência. Classificar
  erros de interpretação, SQL, texto e indisponibilidade.
- [ ] Corrigir os padrões que se repetem e comparar as 24 antes e depois.
  Contar como acerto direto apenas as respostas corretas geradas pelo agente
  sem correção por SQL de referência.

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

- [ ] Dar ao agente um catálogo de métricas, fontes de nota, chaves, relações e
  limites do Gold. Documentar nulidade e como evitar contagens duplicadas.
- [ ] Adicionar 26 casos com filtros combinados, múltiplas métricas,
  comparações por período e cruzamentos de créditos.
- [ ] Avaliar reformulações coloquiais, ambiguidades e seguimentos que
  preservem os filtros anteriores.
- [ ] Melhorar a escrita em português e avaliar separadamente a fidelidade aos
  dados e a clareza da resposta.

### Períodos na fala cotidiana

- [ ] Interpretar “desde 2016” e “de 2016 pra cá” a partir de 1º de janeiro
  de 2016 até a data atual, inclusive, para perguntas sobre filmes já lançados.
  Usar a data de referência da execução. Pedidos explícitos sobre lançamentos
  futuros podem incluir datas posteriores, de acordo com o recorte solicitado.
- [ ] Cobrir “esse ano”, “ano passado” e “nos últimos cinco anos”. Distinguir
  o ano civil anterior de uma janela móvel e usar datas de referência fixas
  na avaliação, incluindo a virada do ano e os limites inclusivos.
- [ ] Avaliar essas expressões em rankings, comparações e perguntas compostas,
  com reformulações reservadas. Em seguimentos como “agora só de 2020 pra cá”,
  atualizar o período e preservar os demais filtros da pergunta anterior.

### Vocabulário de cinema e fala coloquial

- [ ] Cobrir termos comuns em português e empréstimos usados no dia a dia:
  “bilheteria”, “arrecadou”, “custou pra fazer”, “deu prejuízo”, “se pagou”,
  “estreou”, “elenco”, “quem dirigiu”, “animação” e “sci-fi”. Relacionar cada
  expressão aos dados disponíveis e explicar o que o catálogo permite medir.
- [ ] Avaliar frases como “quais bombaram de bilheteria de 2016 pra cá?”,
  “quais floparam mesmo custando caro?” e “quem tá no elenco e quem dirigiu?”.
  Quando “bombou”, “flopou” ou “mais bem avaliado” admitir métricas que mudam
  a resposta, pedir esclarecimento ou explicitar o critério usado.
- [ ] Reservar reformulações com frases curtas, ordem diferente dos pedidos,
  abreviações e erros comuns de digitação. Conferir que o agente preserva
  entidades, filtros e métricas em perguntas simples, compostas e seguimentos
  como “e desses aí, quais se pagaram?”.
- [ ] Usar as frases como casos de avaliação. Ensinar conceitos e relações
  reutilizáveis ao agente e medir a generalização com frases reservadas.

## Rodada 3 · 100 casos

- [ ] Adicionar 50 casos e conferir as referências no Gold. Cobrir rankings,
  períodos, finanças, avaliações, créditos, produtoras e perguntas compostas.
- [ ] Avaliar reformulações reservadas e combinações inéditas. Reportar
  acertos diretos por família e modelo, latência e falhas de API.
- [ ] Confirmar que as 14 originais continuam passando e que todos os 100
  casos têm resultados esperados e critérios explícitos.
- [ ] Montar o painel admin a partir dos registros. Mostrar SQL executado,
  modelo, fallback, tempos e custo informado ou estimado quando houver dados
  suficientes. Exibir acerto em avaliação separado da taxa de sucesso técnico.
