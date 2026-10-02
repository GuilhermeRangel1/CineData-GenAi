# Contrato HTTP do módulo GenAI

Este documento define o contrato mínimo que a API FastAPI deverá cumprir. Ele
é uma decisão de interface entre o módulo GenAI e os consumidores futuros,
incluindo o frontend. A implementação dos endpoints, do agente e do provedor
fica para blocos posteriores.

## Escopo da primeira versão

- Prefixo versionado: `/api/v1`.
- Endpoint principal: `POST /api/v1/questions`.
- Endpoint operacional: `GET /health`.
- Uma requisição representa uma pergunta independente; não há memória de
  conversa, autenticação ou persistência no escopo mínimo.
- O resultado vem exclusivamente da camada Gold consultada pelo serviço. A
  implementação atual já devolve o envelope de sucesso e os metadados descritos
  abaixo.

## Pergunta

`POST /api/v1/questions` recebe JSON:

```json
{
  "question": "Quais são os 10 filmes com maior receita?"
}
```

Regras do campo:

- `question` é obrigatório, texto não vazio e limitado a 1.000 caracteres.
- Espaços nas extremidades podem ser removidos pela API.
- O cliente não envia SQL, nome de tabela, chave de provedor ou configuração
  do modelo.

## Resposta de sucesso

Status HTTP `200`:

```json
{
  "status": "success",
  "answer": "Os filmes foram ordenados pela receita registrada na camada Gold.",
  "rows": [
    {"title": "Exemplo", "revenue": 123456789.0}
  ],
  "metadata": {
    "metric": "receita por filme",
    "source": "gold",
    "query_id": "Q01",
    "unit": "BRL",
    "row_count": 1,
    "truncated": false,
    "period": "todo o Gold disponível",
    "population": "filmes com receita_brl não nula",
    "limitations": "...",
    "columns": ["sk_movie_id", "titulo", "receita_brl"],
    "tool_calls": 1
  }
}
```

Campos:

- `status`: sempre `success` neste formato de resposta.
- `answer`: explicação em português, limitada aos dados retornados.
- `rows`: lista tabular; cada item é um objeto com nomes de coluna estáveis.
  Pode ser vazia quando a consulta válida não encontrar registros.
- `metadata.metric`: identificador estável da métrica respondida, quando
  reconhecido.
- `metadata.source`: `gold` para perguntas analíticas, `platform` para respostas
  baseadas no guia do CineData ou `mixed` quando a pergunta combina as duas
  fontes.
- `metadata.query_id`: identificador Q01–Q14 quando a formulação obrigatória for
  reconhecida.
- `metadata.unit`: unidade ou escala da métrica, quando conhecida.
- `metadata.row_count`: quantidade de linhas retornadas ao consumidor.
- `metadata.truncated`: indica que um limite de segurança reduziu o resultado.
- `metadata.period`: intervalo aplicado, em texto ISO ou `null` quando não se
  aplicar.
- `metadata.population`: população válida usada no cálculo, quando conhecida.
- `metadata.limitations`: limitações semânticas relevantes da métrica.
- `metadata.columns`: colunas retornadas pela consulta validada.
- `metadata.tool_calls`: quantidade de chamadas de ferramenta realizadas.

O contrato não exige que o SQL gerado seja devolvido ao cliente. Para perguntas
Q01–Q14 reconhecidas, o agente valida as colunas esperadas antes de produzir a
resposta final. Se houver uma
necessidade de depuração, ela deverá ser tratada por logs seguros ou metadados
explicitamente autorizados, sem expor segredos, caminhos privados ou traceback.

## Esclarecimento necessário

Status HTTP `422`:

```json
{
  "status": "clarification",
  "error": {
    "code": "ambiguous_question",
    "message": "Informe o período ou a métrica desejada.",
    "details": null
  }
}
```

Esse estado é usado quando a pergunta não determina uma métrica ou filtro
essencial. A API não deve executar uma consulta especulativa para preencher a
lacuna. O modelo pode sinalizar esse estado com `CLARIFY:`; a rota devolve o
envelope acima sem chamar `run_sql`.

## Erros

Todos os erros seguem o mesmo envelope:

```json
{
  "status": "error",
  "error": {
    "code": "gold_unavailable",
    "message": "A base analítica não está disponível.",
    "details": null
  }
}
```

Códigos previstos para a primeira versão:

- `invalid_request` — JSON ausente ou pergunta vazia/longa demais (`400`).
- `ambiguous_question` — informação essencial ausente (`422`).
- `unsupported_question` — pergunta fora do escopo analítico (`422`).
- `gold_unavailable` — arquivo Gold ausente, inválido ou inacessível (`503`).
- `query_rejected` — SQL gerado não passou pelas regras de leitura (`422`).
- `query_timeout` — consulta excedeu o limite definido (`504`).
- `internal_error` — falha inesperada sem detalhes internos (`500`).

As mensagens são próprias para o usuário. Caminhos absolutos, SQL bruto,
credenciais e tracebacks nunca aparecem em `message` ou `details`.

## Health check

`GET /health` retorna `200` quando o processo está ativo:

```json
{"status": "ok"}
```

O health check não valida uma pergunta nem substitui uma verificação explícita
da disponibilidade do Gold. O estado detalhado da base será definido junto da
implementação da conexão.
