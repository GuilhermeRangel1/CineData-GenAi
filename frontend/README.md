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

O endpoint utilizado é `POST /api/v1/questions` do serviço GenAI. A chave do
modelo é configurada no serviço, em `genai/.env`; ela não deve ser colocada em
variáveis `VITE_*` nem enviada ao navegador. O chatbot mostra estados de
carregamento, erro e esclarecimento, além da tabela de resultados e do contexto
da métrica. Cada envio é uma pergunta independente; o histórico visual não é
memória do agente.

## Verificações locais

```powershell
npm test
npm run build
```
