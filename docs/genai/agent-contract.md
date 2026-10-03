# Contrato interno do agente

Este contrato define a fronteira entre `AgentService`, o adaptador de modelo e
as fontes de evidência. O modelo nunca recebe uma conexão SQLite, acesso ao
sistema de arquivos ou uma ferramenta além de `run_sql`.

## Caminhos de resposta

1. Guardrails verificam escopo, instruções adversariais e tentativas de enviar
   SQL diretamente.
2. Perguntas sobre o uso do CineData consultam o guia versionado da plataforma
   e retornam texto, sem SQL e sem chamada ao provedor.
3. Perguntas descritivas sobre filmes podem usar o índice local de títulos e
   sinopses. Se também solicitarem uma métrica, os filmes encontrados viram
   contexto para uma consulta SQL protegida.
4. Perguntas analíticas chegam ao modelo com a ferramenta `run_sql`.
5. O modelo pode solicitar uma única chamada com o argumento `sql`. O serviço
   valida e executa a consulta no Gold e devolve as linhas ao modelo.
6. A resposta final usa apenas as linhas retornadas. Para Q01–Q14, ela inclui
   resposta, métrica, unidade, período, população válida e limitações.
7. Um `CLARIFY:` impede a execução quando faltar uma métrica ou filtro
   essencial. Resultados vazios e pedidos não suportados têm caminhos próprios.

As evidências permanecem em `rows`; `metadata.columns` registra as colunas
validadas. A interface usa essas linhas para tabela e, quando adequado,
gráfico. O serviço de insights recebe somente o resultado estruturado e não
possui acesso ao Gold.

## Porta do provedor

Todo provedor compatível implementa uma operação equivalente a:

```text
complete(messages, tools) -> ModelTurn
```

O adaptador converte essa porta para o SDK escolhido. O orquestrador não deve
importar SDK, chave ou configuração específica do provedor. Em falhas
temporárias previstas, o adaptador tenta uma única vez o modelo de fallback;
falhas de guardrail, validação SQL ou banco não acionam fallback.

## Contexto, cache e privacidade

O frontend envia no máximo três resumos da conversa atual, sem tokens ou dados
da conta. O contexto serve para retomar filtros e métricas em perguntas de
continuação. O `conversation_id` é usado para separar entradas do cache, que
expira em cinco minutos e também invalida quando o Gold ou as regras mudam.

O histórico salvo, criação de conversas e suas permissões são responsabilidades
do backend principal. O GenAI recebe apenas o contexto mínimo de cada chamada.
