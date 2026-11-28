# Contrato HTTP do módulo GenAI

O serviço usa o prefixo `/api/v1`, expõe `GET /health` e recebe perguntas em
`POST /api/v1/questions`. A API não recebe SQL, chaves de provedor, tokens de
sessão ou configuração de modelo do navegador.

`POST /api/v1/questions/stream` aceita o mesmo corpo e retorna
`application/x-ndjson`. A resposta envia eventos de progresso e termina com
um evento de resultado ou erro.

`GET /api/v1/capabilities` retorna `{"analytics_available": true}` quando a
configuração habilita pelo menos um provedor, ou `false` quando nenhum está
configurado. Esse endpoint verifica a configuração local. Sem provedor, perguntas sobre a plataforma
podem responder; consultas a dados, inclusive SQL preparado e busca local,
retornam `provider_not_configured`.

## Requisição

```json
{
  "question": "E qual foi a maior em 2020?",
  "context": [
    {
      "question": "Qual produtora acumulou o maior lucro total em BRL?",
      "metric": "lucro total por produtora",
      "unit": "BRL",
      "period": "todo o catálogo disponível"
    }
  ],
  "conversation_id": "conversa-local-123"
}
```

| Campo | Regra |
| --- | --- |
| `question` | Obrigatório, texto não vazio, até 1.000 caracteres. |
| `context` | Opcional, até dez perguntas resumidas da conversa atual. |
| `conversation_id` | Opcional, entre 12 e 80 caracteres; separa entradas do cache. |

## Sucesso

Status `200`:

```json
{
  "status": "success",
  "answer": "A produtora com maior lucro em 2020 foi ...",
  "rows": [{"produtora": "Exemplo", "lucro_total_brl": 123.45}],
  "insights": ["..."],
  "metadata": {
    "source": "gold",
    "query_id": "Q11",
    "metric": "lucro total por produtora",
    "unit": "BRL",
    "period": "2020",
    "population": "filmes com receita e orçamento informados",
    "limitations": "...",
    "columns": ["produtora", "lucro_total_brl"],
    "row_count": 1,
    "truncated": false,
    "tool_calls": 1,
    "cached": false
  }
}
```

`source` pode ser `gold`, `platform`, `semantic` ou `mixed`. As respostas do
guia da plataforma não requerem linhas; perguntas descritivas podem ter origem
`semantic`; perguntas híbridas combinam busca local e Gold em `mixed`.

## Erros e esclarecimentos

| Status | Código | Quando ocorre |
| --- | --- | --- |
| `422` | validação do FastAPI | Corpo ausente ou campo inválido. |
| `422` | `ambiguous_question` | Falta métrica, período ou detalhe essencial. |
| `422` | `guardrail_rejected` | Pedido adversarial, SQL direto ou fora do escopo. |
| `422` | `unsupported_question` | Função não documentada no CineData. |
| `503` | `provider_not_configured` | Nenhum provedor configurado para a consulta. |
| `503` | `provider_unavailable` | Provedores indisponíveis para concluir a consulta. |
| `503` | configuração ou Gold | Gold indisponível. |
| `504` | `query_timeout` | Consulta excedeu o orçamento de execução. |
| `502` | falha do agente | Erro não recuperável do provedor ou da orquestração. |

Esclarecimentos e erros controlados usam o envelope:

```json
{
  "status": "clarification",
  "error": {"code": "ambiguous_question", "message": "...", "details": null}
}
```

Mensagens públicas não expõem SQL bruto, caminhos, credenciais nem tracebacks.
