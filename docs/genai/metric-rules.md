# Regras das métricas obrigatórias

Este bloco transforma as perguntas da atividade em definições analíticas
verificáveis. As consultas correspondentes estão em
[`reference-queries.sql`](reference-queries.sql). As regras abaixo se baseiam
nas colunas e na qualidade observadas no Gold; quando o enunciado não determina
uma escolha, a decisão adotada fica explicitada para não parecer uma regra
fornecida pela fonte.

## Regras comuns

- **Unidade:** uma linha analítica representa um filme (`sk_movie_id`).
  Bridges podem associar um filme a vários gêneros, pessoas ou produtoras; use
  pares distintos de associação e nunca some fatos depois de um join que
  multiplique filmes sem declarar essa atribuição.
- **Dinheiro:** usar as colunas BRL para todas as métricas financeiras, com
  `receita_brl` e `orcamento_brl`. O arquivo contém campos USD também, mas não
  se misturam moedas na mesma resposta. Não converter valores nem somar os dois
  campos monetários.
- **Lucro:** para métricas que exigem lucro, calcular `receita_brl -
  orcamento_brl` apenas quando ambos existem. Embora o campo `lucro_brl` esteja
  preenchido em todas as linhas, há linhas em que o lucro é informado sem os
  dois componentes; a população financeira verificável é de 1.630 filmes com
  ambos os valores. Nos registros completos, o valor calculado concorda com o
  lucro armazenado dentro de R$ 0,02.
- **Margem:** `(receita_brl - orcamento_brl) / receita_brl`; exigir orçamento,
  receita não nulos e receita maior que zero. Expressar como fração ou percentual
  de forma consistente na resposta (multiplicar por 100 apenas para exibição).
  Forçar aritmética real em SQLite (`1.0 * lucro / receita`), pois colunas
  `NUMERIC` podem conter valores armazenados como inteiros e a divisão inteira
  truncaria casas decimais.
- **Nulos e zeros:** excluir `NULL` quando a métrica exige aquele campo. Não
  converter zero automaticamente em ausente. Notas requerem nota não nula e
  contagem de votos positiva para serem consideradas observadas; nesse caso,
  nota zero é preservada se houver votos.
- **Empates:** ordenar resultados de forma determinística por medida
  decrescente, depois nome/título crescente e chave técnica crescente. Para
  perguntas de “maior” ou “mais”, retornar todos os empatados na primeira
  posição; para top 5/top 10, limitar à quantidade solicitada e usar os
  desempates estáveis.
- **Janela móvel de cinco anos:** lançamento entre `date('now', '-5 years')` e
  `date('now')`, inclusive, usando `data_lancamento`; assim datas futuras não
  entram. Na inspeção em 2026-10-01, o intervalo é 2021-10-01 a 2026-10-01.
  Não usar o ano atual menos quatro como substituto da janela móvel.
- **Perguntas sem período explícito:** usar todo o snapshot disponível no Gold;
  se a análise for sensível a lançamentos futuros ou à data do snapshot,
  declarar essa característica. A janela explícita de cinco anos sempre exclui
  datas posteriores a hoje.
- **Avaliações:** `dim_reviews` é o resumo por filme para quantidade e média
  das avaliações de usuários. `movie_reviews` não contém identificador de
  usuário confiável; não contar pessoas únicas nem inferir evolução temporal a
  partir de `name`/`created_at`.

## Definição por pergunta

| Pergunta | Regra / população |
| --- | --- |
| Top 10 por receita em BRL | Uma linha por filme com `receita_brl` não nula; ordenar pela receita decrescente. Orçamento não é necessário. |
| Lucro médio por gênero | Lucro calculado em BRL quando orçamento e receita existem; calcular a média por gênero associado e informar quantos filmes elegíveis compõem cada média. Um filme associado a mais de um gênero contribui uma vez em cada gênero. |
| Maiores margens | Uma linha por filme elegível à margem; ordenar a fração de margem decrescente. |
| Top 5 mais populares | `popularidade` não nula; zero é mantido como valor. |
| Divergência TMDB/IMDb | Diferença absoluta `ABS(nota_tmdb - nota_imdb)` por filme com ambas as notas não nulas e ambas as contagens de votos positivas. As duas escalas observadas são 0–10. Sem corte mínimo arbitrário de votos; expor as contagens no resultado. |
| Nota IMDb média por ano | Média simples por filme de `nota_imdb` com `qtd_imdb > 0`, agrupada por `ano_lancamento`; informar total de filmes válidos. `ano_lancamento` coincide com o ano extraído de `data_lancamento` em todos os 95.645 filmes inspecionados. |
| Ator com mais filmes nos últimos cinco anos | Tipo `Ator`, associação filme-pessoa distinta e data válida dentro da janela móvel. Contar filmes distintos por pessoa. |
| Diretores com maior nota média (mínimo cinco filmes) | **Decisão adotada porque a pergunta não nomeia a fonte de nota:** usar IMDb (`nota_imdb`) com votos positivos, contar apenas filmes com nota válida e exigir pelo menos cinco filmes válidos por diretor. Uma linha por diretor-filme. |
| Dupla ator-diretor mais frequente | Contar filmes distintos associados simultaneamente a uma pessoa do tipo `Ator` e outra do tipo `Diretor`; retornar pares no máximo. A frequência é coocorrência nas relações Gold, não prova de crédito principal ou ordem nos créditos. |
| Filmes por gênero | Contar filmes distintos associados a cada gênero. |
| Produtora com maior lucro total | Somar lucro calculado em BRL dos filmes elegíveis associados à produtora. Se um filme tem várias produtoras, seu lucro integral é atribuído a cada uma; totais de produtoras não são aditivos entre si. |
| Gênero com maior margem média | Média simples das margens válidas dos filmes associados ao gênero; filme multigênero participa uma vez em cada gênero. Não calcular margem de totais agregados. |
| Filmes mais avaliados por usuários | Usar `dim_reviews.qtd_avaliacoes_usuarios`, ordenação decrescente, uma linha de resumo por filme. |
| Maior divergência entre média de usuários e IMDb | `ABS(nota_media_usuarios - nota_imdb)` por filme com resumo de usuários, quantidade de usuários positiva e nota IMDb com votos positivos. Ambas as notas observadas estão em 0–10. |

## Limites semânticos identificados

- O mínimo de cinco para diretores é aplicado a filmes com nota IMDb elegível,
  não à filmografia completa sem nota; isso evita calcular uma média apoiada em
  menos de cinco observações. Se a interpretação pretendida for cinco filmes
  totais, a definição precisa mudar antes de implementar as consultas do agente.
- As dimensões Gold não distinguem elenco principal, aparições pequenas,
  co-produtoras ou produtora principal. Métricas de pessoas e produtoras refletem
  exatamente associações presentes nas bridges.
- A divergência TMDB/IMDb mais alta encontrada inclui notas baseadas em apenas
  um voto. Como a atividade não define um limite mínimo, não foi inventado um;
  a consulta retorna as contagens junto com a diferença para contextualizar.
- A margem máxima por filme fica próxima de 100%, mas algumas margens são muito
  negativas devido a receita positiva pequena frente ao orçamento. A média de
  margens por gênero é sensível a esses valores; sem regra de corte no enunciado,
  não foram removidos nem limitados (winsorized).
- `dim_reviews` e `movie_reviews` concordam na contagem dos filmes e quantidade
  de reviews nos dados inspecionados; a média do resumo é arredondada com delta
  máximo observado de aproximadamente 0,005. Usar o resumo é suficiente para as
  perguntas agregadas e evita recalcular todas as avaliações textuais.
- As 14 consultas Q01–Q14 em `reference-queries.sql` foram executadas contra o
  Gold em conexão SQLite somente leitura; todas retornaram resultados. A
  consulta de coocorrência ator-diretor é a mais custosa (cerca de 30 segundos
  nesta máquina) e merece uma otimização específica antes de ser usada em
  respostas interativas.
- As regras e SQL devem ser executadas novamente na etapa de validação após
  qualquer troca de arquivo Gold. Este documento não autoriza escritas na base.
