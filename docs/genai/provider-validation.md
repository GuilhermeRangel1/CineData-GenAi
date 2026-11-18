# Validação real de provedores

Os testes automatizados verificam o roteador com transportes simulados. As avaliações abaixo também fizeram chamadas reais e executaram o SQL gerado no Gold por meio do mesmo executor somente leitura do aplicativo.

## Configuração e comandos

Credenciais ficam somente em `genai/.env`, ignorado pelo Git. Não as envie por chat nem as inclua em relatórios.

```dotenv
GENAI_PROVIDER_ORDER=gemini,groq,openrouter
GENAI_GEMINI_API_KEY=
GENAI_GROQ_API_KEY=
GENAI_GROQ_MODEL=
GENAI_OPENROUTER_API_KEY=
GENAI_OPENROUTER_MODEL=
```

Groq e OpenRouter exigem chave e modelo explícito com suporte a tool calling. Depois de mudar o arquivo, recrie o serviço:

```powershell
docker compose up -d --no-build --no-deps genai
```

O smoke test real de tool calling pode ser executado por rota:

```powershell
docker compose exec -T genai python -m app.provider_check --order groq
docker compose exec -T genai python -m app.provider_check --order openrouter
```

Para avaliar Q01–Q14 sem cache e sem recuperação por consulta de referência, use `genai/scripts/evaluate_live_providers.py` com `--model-only` e um único provedor por rodada. O avaliador compara a saída com o Gold depois que o agente responde; a referência não substitui o resultado do modelo. Insights ficam desativados nessa avaliação para limitar chamadas.

## Rodada anterior à correção de Q08

| Provedor e modelo | Acertos diretos | Situação da rodada |
| --- | ---: | --- |
| Groq `openai/gpt-oss-20b` | 14/14 de primeira | Rodada completa; SHA256 `6c532a178d30170419b364ed8bcc2bb4400c239e54f8f403a071994793cbe33c` |
| OpenRouter `nvidia/nemotron-3.5-lightning:free` | 8/14 confirmados | Q01–Q08 passaram; Q09 expirou o timeout de novo na chamada isolada. Relatório parcial e [repetição de Q09](openrouter-q09-retry-2026-11-18.json) usam o mesmo SHA256; nenhuma SQL foi gerada na repetição. |

Todas as avaliações usaram `model_only=true`; respostas aprovadas têm
`query_source=model`. A consulta Gold é executada pelo avaliador somente depois
da resposta, para comparar resultados. Ela nunca substitui a consulta do modelo.

- [Groq Q01–Q14, versão atual](groq-final-2026-11-18.json)
- [OpenRouter, rodada parcial com a versão atual](openrouter-current-partial-2026-11-18.json)
- [OpenRouter 14/14 numa imagem anterior](openrouter-previous-image-14-of-14-2026-11-18.json): excluído da contagem atual porque usou uma cópia antiga de `agent.py`.
- [Paráfrases Q03/Q12 no Groq](groq-final-paraphrases-2026-11-18.json) e [pergunta nova top 3](groq-novel-prior-agent-2026-11-18.json), testadas antes do ajuste final de Q06. A tentativa de repetição no contexto atual falhou antes de gerar SQL por erro transitório do provedor.
- [Avaliação inicial com recuperação por referência](live-provider-results-2026-11-18.json), anterior aos ajustes de precisão.

Na versão de SHA256 `6c532a…`, a rodada Groq confirmou Q01–Q14 de primeira.
O OpenRouter completou as perguntas depois, em rodadas sucessivas descritas abaixo.
O relatório da imagem antiga continua excluído dessa contagem.

## Limitações e pendências externas

- Gemini foi validado após remover a atribuição duplicada do `.env`; a chave em si era válida. A falha de Q08 foi corrigida e testada nos três provedores, conforme as seções abaixo.
- A avaliação confirma resultados tabulares no Gold atual; não garante respostas corretas para todo enunciado ou conjunto de dados.
- O smoke test Groq ↔ OpenRouter com falha simulada foi aprovado. A disponibilidade e as cotas dependem das contas dos provedores.
- O OpenRouter completou Q01–Q14 em rodadas sucessivas na versão anterior ao ajuste de Q08. Houve timeouts entre tentativas; o diagnóstico de 30 segundos foi temporário, sem alterar o limite normal.
- Os testes automatizados locais passaram (192 testes GenAI e Ruff sem erros na revisão registrada).


## Retomada com chave atual

Q09 passou diretamente em 23,67 segundos totais, incluindo SQL; o timeout da
API continuou em 12 segundos. Q10, Q11, Q13 e Q14 passaram diretamente na
continuação. Q12 expirou no limite de 12 segundos e passou numa repetição de
diagnóstico com limite de 30 segundos: HTTP 200 em 5,29 segundos, total 5,42.
Isso indica variação entre tentativas; não demonstra que elevar o timeout foi
necessário, pois a repetição respondeu antes dos 12 segundos originais.
Não houve erro de cota nessa continuação. A causa dos timeouts anteriores não
pode ser atribuída à cota nem à chave com base nos dados disponíveis.

Todas as Q01–Q14 tiveram resultado direto aprovado nessa versão, reunindo
rodadas sucessivas. Isso não representa uma rodada única 14/14 no OpenRouter.
A configuração normal de timeout foi preservada.
Relatórios adicionais: `openrouter-q09-latest-2026-11-18.json`,
`openrouter-q10-q14-2026-11-18.json` e `openrouter-q12-timeout30-2026-11-18.json`.


## Gemini: configuração corrigida e avaliação real

A chave era válida. O valor salvo continha uma segunda atribuição
`GENAI_GEMINI_API_KEY=` dentro do valor da variável. A duplicação foi removida
somente no `.env` local; nenhum segredo foi versionado. A API direta retornou
HTTP 200 e o smoke test confirmou a contagem de 95.645 filmes.

Q01–Q14 foram executadas com Gemini isolado, modo `model_only` e insights
desativados. Resultado da rodada: 11 acertos de SQL na primeira tentativa,
Q04 correta após reparo pelo próprio modelo, Q02 com timeout e Q08 incorreta.
Na repetição, Q02 passou e Q08 continuou incorreta: retornou 100 diretores,
contra os dois empatados na maior média exigidos pelo gabarito.
Antes da correção descrita na próxima seção, 13/14 chegaram ao resultado correto
em rodadas sucessivas e Q08 estava pendente. Nenhuma aprovação utilizou SQL de referência.
O modelo complexo `gemini-3.5-flash` apresentou ServerError em algumas chamadas,
e o adaptador tentou `gemini-3.5-flash-lite`. Os registros `model` do avaliador
indicam o modelo principal configurado, não necessariamente o modelo interno
que efetivamente respondeu após fallback Gemini.
Relatórios: `gemini-current-2026-11-18.json` e `gemini-retry-2026-11-18.json`.
As afirmações anteriores de chave rejeitada descrevem o valor duplicado,
não a validade da chave removida dessa duplicação.


## Correção de Q08 no Gemini

O Gemini interpretava o pedido de maior média como ordenação de todos os
diretores elegíveis. A instrução específica de Q08 passou a exigir agregação
separada e filtro externo da média igual ao máximo, preservando todos os
empatados. Não foi adicionada consulta pronta ao executor nem recuperação por
referência no modo de avaliação.

Depois do ajuste, Q08 passou em duas chamadas independentes ao Gemini e em
uma chamada a cada um de Groq e OpenRouter. Todas retornaram os dois diretores
corretos, com `query_source=model`, sem reparo ou SQL de referência.
SHA256 do agente: `e501bd3b42f60c43f4ce361a44891c91613d2ff1f9d98c1ef95ecc5738291f60`.
Relatórios: `gemini-q08-fixed-2026-11-18.json` e
`providers-q08-fixed-2026-11-18.json`.

Verificação local: 192 testes passaram e Ruff sem erros no arquivo alterado.
Este ajuste foi validado em Q08; não representa nova rodada integral Q01–Q14
na versão posterior ao ajuste. A primeira rodada do Gemini continua registrada
como 12/14; somando as repetições e a correção, todas as 14 têm resultado correto
observado, com Q04 precisando de reparo pelo modelo na rodada anterior.
A alteração de Q08 e os relatórios são versionados em commits separados por escopo.
