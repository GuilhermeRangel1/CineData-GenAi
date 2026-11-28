# Contrato proposto — Observabilidade do GenAI

Rascunho para revisão antes da implementação. Os caminhos abaixo pertencem à API autenticada do CineData.

| Método e caminho | Acesso | Resultado |
| --- | --- | --- |
| `GET /api/v1/admin/analytics/genai/resumo` | Admin | Indicadores, evolução diária e uso por modelo no período. |
| `GET /api/v1/admin/analytics/genai/perguntas` | Admin | Histórico paginado com hora, ID, rota, status, duração e custo estimado. |
| `GET /api/v1/admin/analytics/genai/perguntas/{request_id}` | Admin | Registro e tempos por etapa, SQL permitido, linhas retornadas e chamadas ao modelo, incluindo tentativas e fallbacks. |
| `GET /api/v1/minha-conta/genai/perguntas/{request_id}/detalhes` | Conta proprietária | Duração total, fontes, filtros e SQL executado quando a rota e as permissões permitirem. |

## Autorização e integração

- Validar o papel atual da conta no backend com `get_current_admin`. Para o chat, validar a sessão e conferir o proprietário do registro antes de montar a resposta. A projeção do chat contém apenas os campos listados na tabela.
- Derivar a identidade da sessão validada, por um canal autenticado entre os serviços. O cliente pode receber e usar o ID da pergunta, e o backend resolve a identidade da conta independentemente desse ID.
- Manter operações internas de telemetria fora dos caminhos públicos do proxy `/genai` e exigir autenticação entre serviços. Guardar telemetria fora da base Gold.
- Usar o mesmo ID para resposta direta e streaming, com um único estado final por pergunta. Preservar o formato dos eventos NDJSON existentes, expondo o ID como campo adicional do resultado quando aplicável.
- Omitir prompts completos e segredos. Persistir e devolver apenas SQL com conteúdo autorizado e literais sensíveis tratados.

## Campos e filtros

- **Resumo.** Aceita `periodo_dias` de 7, 30 ou 90, com padrão de 30. Retorna `periodo_dias`, `metricas`, `evolucao` e `modelos`. As métricas incluem `perguntas`, `chamadas_modelo`, `latencia` (p50, p95 em milissegundos e tamanho da amostra), `erros` (quantidade, taxa e base), `cache` (acertos, taxa e base) e `custo_estimado` (valor, moeda, chamadas com custo e total de chamadas). A evolução traz data, volume, p95 e custo estimado. O uso por modelo traz provedor, modelo, chamadas, tokens de entrada e saída, custo estimado, moeda e chamadas com custo.
- **Histórico.** Aceita o mesmo período e os filtros `rota`, `provedor`, `modelo`, `status`, `pagina` e `tamanho_pagina`, com limite de tamanho na API. Retorna `pagina`, `tamanho_pagina`, `total` e `itens`, do mais recente ao mais antigo. Cada item inclui `request_id`, `criada_em`, `rota`, `status`, `duracao_ms`, `cache_hit`, `chamadas_modelo`, `custo_estimado`, `moeda` e `chamadas_com_custo`. Quando provedor e modelo forem filtrados juntos, ambos devem corresponder à mesma tentativa.
- **Detalhe administrativo.** Retorna `request_id`, `iniciada_em`, `finalizada_em`, `rota`, `status`, `duracao_total_ms`, `cache_hit`, `origem`, `etapas`, `tentativas`, `sql_gerado`, `sql_executado` e `linhas_retornadas`. Uma etapa tem nome, duração e status. Uma tentativa tem provedor, modelo, duração, status, tokens, custo estimado, moeda, código de erro e indicação de fallback.
- **Detalhe no chat.** Retorna `request_id`, `duracao_ms`, `origem`, `filtros`, `sql_executado` e `linhas_retornadas`. Campos sem aplicação ou cuja divulgação seja restrita podem ser nulos. A associação verificada com a conta deve existir antes de expor o endpoint.
- **Dados ausentes.** Usar `null` para custo indisponível ou tokens não reportados. Zero é válido para custos conhecidos ou respostas sem chamada ao modelo. Custos parciais acompanham a contagem de chamadas cobertas e o total. Status terminais previstos são `sucesso`, `erro`, `timeout` e `cancelada`.

## Erros

Preservar o envelope do backend `{error: {code, message, details}}`. Responder com 401 para sessão ausente ou inválida, 403 para acesso administrativo negado, 404 para registro inexistente ou pertencente a outra conta, 422 para filtros inválidos e 503 para indisponibilidade da telemetria. Falhas inesperadas têm resposta genérica. O mesmo 404 cobre registros ausentes e registros de outra pessoa para evitar revelar sua existência.
