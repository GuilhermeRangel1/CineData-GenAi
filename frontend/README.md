# Frontend CineData

Interface React + TypeScript + Vite para o catálogo e os recursos sociais do
CineData. O chatbot usa o mesmo visual do site e consulta o serviço GenAI por
HTTP; não chama o provedor diretamente do navegador.

## Execução local

Na raiz do projeto, inicie backend e GenAI com Docker Compose. Em outro
terminal:

```powershell
cd frontend
npm ci
npm run dev
```

O Vite fica em `http://localhost:5173`. O frontend espera o backend em
`http://localhost:8000/api/v1`; por padrão, as chamadas do chatbot passam por
`/genai/api/v1`. No Compose o Nginx encaminha essa rota ao GenAI e, no Vite, o
proxy de desenvolvimento envia as chamadas a `http://localhost:8001`.
`VITE_API_BASE_URL` e `VITE_GENAI_API_BASE_URL` podem alterar esses endereços.

## Chatbot

O chat usa `POST /api/v1/questions/stream` do serviço GenAI para receber
progresso e resultados. Configure as credenciais dos provedores em
`genai/.env`. O chatbot mostra estados de
carregamento, erro e esclarecimento, além de tabela, gráfico, insights e
contexto da métrica. Para perguntas de continuação, o frontend envia no máximo
dez resumos da conversa atual, sem tokens ou dados da conta. Usuários
autenticados podem salvar, retomar, renomear e excluir conversas; o modo
temporário não persiste mensagens. A aba Ajuda inclui 47 das 50 perguntas
oficiais. Veja o [guia do frontend](../docs/frontend.md#chatbot) e o
[contrato HTTP](../docs/genai/api-contract.md).

## Verificações locais

```powershell
npm test
npm run build
```
