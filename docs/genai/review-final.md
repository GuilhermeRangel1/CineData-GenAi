# Revisão final da entrega GenAI

Revisão realizada em 03/10/2026, comparando o projeto com o enunciado do Rocket Lab.

Esta revisão registra as verificações daquela data. Melhorias posteriores na
busca por sinopse e na linguagem exibida pelo chatbot estão descritas no README
principal; os números de testes abaixo não representam uma nova execução após
essas alterações.

## Entregas obrigatórias

- Serviço Python FastAPI integrado ao CineData: confirmado em `genai/app` e no Compose.
- Perguntas em linguagem natural sobre o catálogo: confirmadas pela rota `/api/v1/questions` e pelo chatbot.
- Leitura segura da Gold SQLite: `sql_guard.py` aceita somente `SELECT` autorizado e o executor abre o banco em modo somente leitura.
- Cobertura Q01 a Q14: os casos, consultas de referência e resultados esperados estão versionados em `docs/genai`; a execução local `evaluate_agent_snapshot.py` validou os casos contra o Gold.
- README de execução e versionamento: confirmado na raiz do repositório.

## Fluxos e extras revisados

- Interface de chat, ajuda, respostas textuais, tabelas, gráficos e exportações.
- Guardrails para SQL direto, instruções adversariais e pedidos fora de escopo.
- Cache por conversa, memória resumida, conversa temporária e histórico persistente.
- Busca híbrida por sinopses, fallback em falhas transitórias, roteamento por complexidade e progresso da resposta.

## Evidências de execução

- Suíte GenAI: 119 testes aprovados; `ruff check` sem avisos.
- Suíte do frontend: 66 testes aprovados; `npm run build` aprovado.
- `docker compose config -q`: aprovado.
- Avaliação Q01–Q14 com o banco do serviço: 14 resultados iguais às referências em 3,5 s.
- Saúde dos serviços: backend e GenAI saudáveis; frontend retornou HTTP 200.
- Pela rota pública do frontend, Q10 retornou 19 linhas e Q05 retornou 10 linhas após geração de SQL pelo modelo.
- O fluxo de progresso entregou eventos até a resposta textual sobre o catálogo; tentativa de `DROP TABLE` recebeu `guardrail_rejected` (422).
- Busca de sinopses retornou resultados e a consulta híbrida respondeu sem falha de serviço; um recorte sem dados numéricos retornou tabela vazia, como esperado.
- Gold disponível no serviço GenAI com as 10 tabelas analíticas esperadas; `alembic_version` é metadado adicional do arquivo.

## Correções da revisão

- O avaliador agora usa `GENAI_GOLD_DATABASE_PATH` quando definido. No Docker, isso evita medir a base montada do Windows em vez da cópia local que atende às perguntas.
- O fallback da rota complexa usa e registra o modelo alternativo efetivamente selecionado.
- O índice de sinopses faz uma reconstrução por vez e trata ausência do banco como indisponibilidade controlada.
- O streaming tem cobertura de sucesso e rejeição pelo guardrail.
- Visitantes podem iniciar outra conversa temporária sem recarregar a página; o campo de texto respeita o limite de 1.000 caracteres da API.
- O cliente do streaming recompõe eventos divididos entre pacotes e mostra erro legível quando recebe dados inválidos ou a conexão cai.
- A resposta mista sobre plataforma e filmes não exibe a expressão interna “Gold”.

## Observação operacional

A imagem de produção não inclui `pytest` nem os scripts de avaliação, por decisão de reduzir a imagem. As avaliações devem ser executadas pelo comando documentado com o código-fonte disponível, sem depender da chave Gemini.

Os testes automatizados usam modelos simulados. A validação ao vivo cobriu Q05 com a chave configurada, além de rotas locais, texto, busca de sinopses e guardrail; ela não garante que toda formulação livre do modelo produzirá SQL correto.
