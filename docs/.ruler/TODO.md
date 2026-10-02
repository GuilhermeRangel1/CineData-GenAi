# CineData GenAI — plano de execução

Este plano acompanha os requisitos obrigatórios em etapas amplas, seguindo a
organização do TODO original do CineData Fullstack. Os commits podem acontecer
em pontos coesos dentro de cada etapa; o checklist não precisa registrar cada
checkpoint intermediário.

## Direção do projeto

- O GenAI é um serviço Python/FastAPI próprio, separado do backend social e do
  catálogo.
- As consultas usam o Gold SQLite em modo somente leitura. A chave do provedor
  fica no backend e nunca é enviada ao navegador.
- Preservar as funcionalidades e o design do CineData; substituir apenas o
  fluxo antigo do chatbot quando a integração nova estiver pronta.
- O limite disponível é de até 50 chamadas diárias. Para desenvolvimento,
  preferir no máximo 5 chamadas reais por dia, sem repetição automática.

## 1. Dados e regras das métricas

- [x] Confirmar e inspecionar `data/cinerocket.db`; registrar tabelas,
      relacionamentos, chaves, tipos, nulos e cardinalidades relevantes em
      [`genai/gold-schema.md`](../genai/gold-schema.md).
- [x] Definir fórmulas, população válida, tratamento de nulos, períodos,
      escalas, joins e desempates das métricas obrigatórias.
- [x] Escrever e conferir no Gold as consultas de referência para as 14
      perguntas obrigatórias.

**Critério de saída:** esquema e métricas estão documentados e cada pergunta
obrigatória tem uma consulta de referência validada. Consulte
[`genai/metric-rules.md`](../genai/metric-rules.md) e
[`genai/reference-queries.sql`](../genai/reference-queries.sql).

## 2. Serviço GenAI e acesso seguro ao Gold

- [x] Criar o módulo FastAPI isolado, com configuração, dependências e health
      check próprios.
- [x] Definir o contrato HTTP para perguntas, respostas, metadados, tabelas e
      esclarecimentos.
- [x] Implementar conexão configurável ao Gold com SQLite somente leitura,
      timeout e erros compreensíveis.
- [x] Implementar ferramenta SQL com tabelas permitidas, uma consulta por vez,
      limite de resultados e bloqueio de escrita e comandos externos.
- [x] Cobrir conexão, validação e execução com testes locais determinísticos.

**Critério de saída:** o serviço acessa o Gold por uma interface somente
leitura e rejeita SQL fora dos limites definidos. Os testes da ferramenta não
dependem de rede nem de chave externa.

## 3. Agente e perguntas obrigatórias

- [x] Implementar o fluxo pergunta → tool calling → validação → consulta →
      interpretação dos resultados → resposta em português, usando o adaptador
      Gemini configurável por ambiente.
- [x] Fazer o agente responder com base nos resultados retornados pela
      ferramenta, apresentando métrica, unidade, período, população e
      limitações; pedir esclarecimento quando faltar uma métrica essencial.
- [x] Cobrir as 14 perguntas obrigatórias: finanças; popularidade e notas;
      elenco e equipe; gêneros e produtoras; avaliações de usuários.
- [x] Criar avaliações locais com resultados esperados do Gold e comparar os
      valores com as consultas de referência.
- [x] Usar mocks nas avaliações locais e limitar chamadas reais ao provedor,
      sem retries automáticos.

**Critério de saída:** as perguntas obrigatórias passam pelas avaliações locais
e respeitam as regras semânticas e os limites de uso. Perguntas ambíguas devem
ser esclarecidas sem executar SQL.

## 4. Interface do chatbot

- [x] Reutilizar o layout do site para entrada de pergunta, carregamento, erro,
      resposta, metadados e tabela de resultados.
- [x] Integrar a interface ao endpoint GenAI sem expor a chave nem chamar o
      provedor pelo navegador.
- [x] Remover o endpoint e a integração Gemini antigos do backend, mantendo
      as demais funcionalidades existentes.
- [x] Validar manualmente uma pergunta de ponta a ponta pela interface.

**Critério de saída atendido:** a pessoa consegue enviar uma pergunta pela
interface e ver a resposta e seus resultados; os estados de erro e
esclarecimento também têm cobertura local. A apresentação continua coerente com
o restante do CineData.

## 5. Operação e entrega

- [x] Configurar e validar `docker compose up` (sem `--build`) para construir
      as imagens e iniciar os quatro serviços no checkout atual.
- [x] Repetir a inicialização em clone limpo para confirmar o preparo completo
      do projeto e do banco operacional.
- [x] Verificar o objeto Gold via Git LFS no checkout atual e documentar
      instalação do Git LFS e obtenção do arquivo em um clone novo.
- [x] Atualizar README e tooling com instalação, configuração segura, execução
      e uso do chatbot.
- [x] Conferir que `.env` e o banco operacional local estão ignorados e que
      somente o Gold e os exemplos de ambiente são versionados intencionalmente.
- [x] Fazer smoke check sem escrita no catálogo e nos health checks depois do
      rebuild.
- [x] Revalidar as funcionalidades existentes da aplicação após a migração do
      banco com a suíte de regressão e uma cópia descartável para testes que
      alterem dados.
- [ ] Publicar no GitHub somente com autorização explícita.

**Critério de saída:** a aplicação completa inicia conforme as instruções de
clone e mantém as funcionalidades anteriores; documentação e arquivos
versionados correspondem ao estado entregue.

## Depois dos requisitos obrigatórios

Considerar como extras, conforme prazo e benefício: memória de conversa,
cache, fallback de provedor, busca semântica descritiva, gráficos e avaliações
ampliadas. Não bloqueiam a entrega obrigatória.
