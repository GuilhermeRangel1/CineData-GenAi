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

## Resultados com a versão atual do agente

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

A rodada Groq confirma a geração direta para Q01–Q14 no código publicado. A
validação completa do OpenRouter nessa mesma versão depende de a API gratuita
voltar a responder sem timeout/limite. A rodada anterior de 14/14 não serve para
confirmar a versão atual do agente.

## Limitações e pendências externas

- Gemini isolado não foi validado: a chave usada foi rejeitada pela API (HTTP 400). Uma chave válida é necessária para repetir o teste.
- A avaliação confirma resultados tabulares no Gold atual; não garante respostas corretas para todo enunciado ou conjunto de dados.
- O smoke test Groq ↔ OpenRouter com falha simulada foi aprovado. A disponibilidade e as cotas dependem das contas dos provedores.
- O OpenRouter chegou a responder HTTP 200 e completar rodadas com imagens anteriores; na rodada do código atual, Q09 expirou o timeout e a API deixou de responder às chamadas seguintes.
- Os testes automatizados locais passaram (192 testes GenAI e Ruff sem erros na revisão registrada).
