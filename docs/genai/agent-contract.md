# Contrato interno do agente

Este contrato define a fronteira entre o orquestrador do agente e qualquer
framework/provedor de modelo. Ele não escolhe uma empresa ou modelo e não faz
chamadas externas.

## Fluxo mínimo

1. O serviço recebe uma pergunta em português.
2. O modelo recebe a pergunta e a ferramenta `run_sql`.
3. O modelo pode solicitar exatamente uma chamada dessa ferramenta, com um
   argumento `sql`.
4. O serviço valida e executa o SQL pela camada Gold já protegida.
5. O resultado tabular volta ao modelo para uma resposta final em português.
6. A resposta do serviço mantém as linhas retornadas e a indicação de
   truncamento.

O modelo não recebe acesso direto ao arquivo, à conexão SQLite ou a outras
ferramentas. O orquestrador também não aceita uma resposta factual sem que a
consulta tenha sido executada.

## Porta do provedor

Um adaptador de provedor deve implementar apenas uma operação equivalente a:

```text
complete(messages, tools) -> ModelTurn
```

O adaptador converte o formato dessa porta para o SDK escolhido. O restante do
serviço não deve importar SDK, chave, nome de modelo ou configuração de
provedor. Os testes usam um modelo simulado e não consomem cota.

## Limites deste bloco

Memória de conversa, seleção de modelo, retries, fallback, streaming, busca
semântica e integração FastAPI ficam para blocos posteriores. Uma pergunta usa
no máximo um tool call nesta primeira versão para manter custo, rastreabilidade
e controle de cota previsíveis.
