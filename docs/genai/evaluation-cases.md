# Casos de avaliação das perguntas obrigatórias

Este catálogo transforma as 14 perguntas obrigatórias em casos identificáveis
para testes locais. Cada caso aponta para a consulta de referência equivalente
em [`reference-queries.sql`](reference-queries.sql) e define as colunas que o
resultado deve conter.

O avaliador deve comparar os valores e as regras da métrica com o resultado da
consulta de referência. Não deve exigir que o SQL gerado pelo modelo seja igual
ao SQL de referência: consultas equivalentes podem usar aliases, CTEs ou
ordenações internas diferentes e ainda produzir o mesmo resultado correto.

| Caso | Tema | Consulta | Colunas esperadas |
| --- | --- | --- | --- |
| Q01 | Top 10 por receita BRL | Q01 | `sk_movie_id`, `titulo`, `receita_brl` |
| Q02 | Lucro médio por gênero | Q02 | `nome_genero`, `filmes_elegiveis`, `lucro_medio_brl` |
| Q03 | Maiores margens | Q03 | `sk_movie_id`, `titulo`, `margem` |
| Q04 | Top 5 por popularidade | Q04 | `sk_movie_id`, `titulo`, `popularidade` |
| Q05 | Divergência TMDB/IMDb | Q05 | `sk_movie_id`, `titulo`, `divergencia`, notas e votos |
| Q06 | IMDb médio por ano até a data atual | Q06 | `ano_lancamento`, `filmes_validos`, `nota_imdb_media` |
| Q07 | Ator em mais filmes na janela | Q07 | pessoa, nome e `total_filmes` |
| Q08 | Diretores com maior média IMDb | Q08 | pessoa, filmes válidos e `nota_media` |
| Q09 | Dupla ator-diretor | Q09 | `ator`, `diretor`, `filmes_em_comum` |
| Q10 | Filmes por gênero | Q10 | `nome_genero`, `total_filmes` |
| Q11 | Lucro total por produtora | Q11 | produtora, filmes elegíveis e `lucro_total_brl` |
| Q12 | Maior margem média por gênero | Q12 | gênero, filmes válidos e `margem_media` |
| Q13 | Mais avaliações de usuários | Q13 | filme e `qtd_avaliacoes_usuarios` |
| Q14 | Divergência usuários/IMDb | Q14 | filme, notas, votos e `divergencia` |

O catálogo está em `genai/app/evaluation_cases.py` e não faz chamadas ao
provedor. A execução real deve continuar limitada a validações manuais pequenas;
os testes automatizados usam modelos simulados.

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
