# TODO — CineData GenAI

Plano de execução da atividade. A etapa 1 está sendo feita em blocos pequenos,
com checkpoints revisáveis para commit. Integridade, inventário, regras das
métricas e consultas de referência já foram trabalhados; faça a revisão do
checkpoint atual antes de iniciar qualquer tarefa da etapa 2.

## Direção acordada

- O agente será um módulo Python com API própria em FastAPI, separado do backend
  social/catálogo existente. A pasta e o serviço devem ter dependências,
  configuração, testes e ciclo de execução próprios.
- O módulo consultará a camada Gold SQLite em modo somente leitura. O arquivo
  `cinerocket.db` será distribuído via Git LFS para estar disponível no clone;
  nunca copiá-lo para a imagem Docker.
- Até a conclusão da etapa 1, não implementar serviço/API GenAI, agente,
  provedor/modelo, chamadas externas nem integração de interface. Preserve o
  chatbot e as funcionalidades existentes durante esta etapa.
- Critério operacional desejado: depois do clone/preparo inicial, um único
  `docker compose up --build` inicia frontend, aplicação existente e serviço
  GenAI; dados persistentes ficam em diretório do projeto ignorado pelo Git,
  sem depender de volume Docker opaco.
- O Gold real é distribuído via Git LFS. Instalação/checkout LFS faz parte do
  preparo do clone; o Compose valida o arquivo antes de inicializar a API. Nunca
  substituir o Gold por dados fake.
- Provedor, framework, credenciais, limites de chamadas e desenho da API não
  estão decididos. Revisar esses pontos antes de iniciar qualquer implementação.
- Construir em ordem: entendimento e regras -> ferramenta SQL segura -> agente
  com tool calling -> cobertura das perguntas obrigatórias -> integração visual
  -> documentação/entrega. Extras só entram depois do critério obrigatório.
- Desenvolvimento e testes rotineiros devem ser locais, determinísticos e sem
  chamadas ao provedor. A cota informada é de até 50 chamadas por dia: chamadas
  reais ficam limitadas a uma rodada manual curta, com orçamento recomendado de
  no máximo 5 por dia de desenvolvimento e nunca em loop/retry automático.

## 1. Base de dados e semântica das métricas

- [x] Confirmar `data/cinerocket.db` como Gold local e inspecionar sua
      integridade (`integrity_check = ok`; `foreign_key_check` sem violações).
- [x] Inventariar colunas, chaves, tipos, nulos e cardinalidades necessários
      para as perguntas da atividade; registrar o mapa em
      [`../genai/gold-schema.md`](../genai/gold-schema.md). A validação das
      fórmulas e consultas continua pendente nos itens abaixo.
- [x] Fixar as regras analíticas antes de gerar SQL: receita é o valor de
      receita do filme; lucro = receita - orçamento quando ambos são conhecidos;
      margem = lucro / receita somente com receita maior que zero.
- [x] Excluir valores ausentes das métricas que dependem deles e informar a
      população usada; zero não deve ser tratado como valor ausente sem evidência.
- [x] Para “últimos cinco anos”, usar janela móvel de cinco anos a partir da
      data atual, baseada na data de lançamento válida, e declarar o intervalo.
- [x] Para divergência entre notas, usar diferença absoluta apenas após
      confirmar que as fontes têm escalas comparáveis; não comparar escalas
      incompatíveis sem normalização explícita e validada.
- [x] Usar filmes distintos em contagens de participação; em empates, ordenar
      por nome/título de forma estável e expor o empate quando relevante.
- [x] Validar joins 1:N e bridges agregando fatos no nível do filme antes de
      somar receita/lucro por gênero, pessoa ou produtora.
- [x] Distinguir avaliações de usuários das notas externas conforme a tabela e
      as relações reais do Gold; não inferir origem só pelo nome da coluna.
- [x] Conferir as regras com SQL de referência e amostras do Gold; ajustar as
      decisões acima se o esquema ou o enunciado exigir outro significado.

**Critério de saída atendido neste checkpoint:** esquema e relações documentados;
cada métrica obrigatória tem fórmula, população, filtros de nulos, período
aplicável e desempate definidos; as 14 consultas de referência retornaram
resultados no Gold. Consulte [`../genai/metric-rules.md`](../genai/metric-rules.md)
e [`../genai/reference-queries.sql`](../genai/reference-queries.sql). Rever as
decisões documentadas antes de iniciar a etapa 2.

## 2. Módulo backend GenAI — ainda não iniciar

**Entrada:** somente após completar os critérios de saída da etapa 1 e revisar
com o usuário um checkpoint contendo as regras e consultas de referência.

- [ ] Criar bloco isolado em `genai/` com FastAPI própria,
      dependências/configuração próprias e limites claros em relação ao backend
      atual. O módulo não deve importar modelos, rotas ou estado social do app.
- [ ] Definir contrato HTTP pequeno para pergunta, estado/erro, resposta,
      metadados úteis e resultado tabular; não exigir autenticação ou memória no
      escopo mínimo sem necessidade do enunciado.
- [ ] Implementar conexão ao Gold por caminho configurável, SQLite `mode=ro`,
      timeout e tratamento claro de base ausente/inválida.
- [ ] Implementar ferramenta SQL tipada: permitir uma consulta, somente leitura,
      somente tabelas Gold necessárias, limite de linhas e tempo; bloquear escrita,
      DDL, múltiplas instruções, `ATTACH`/`DETACH` e acesso externo.
- [ ] Validar SQL com parser adequado a SQLite e reforçar a proteção na própria
      conexão somente leitura; validação recusada nunca chega a ser executada.
- [ ] Implementar testes determinísticos com SQLite temporário para permissões,
      limites, erros e consultas; sem depender de rede nem chave de provedor.

**Critério de saída:** API isolada, contrato e ferramenta de leitura Gold
implementados e verificados localmente. Esta etapa só começa após a saída da
etapa 1 e o checkpoint acordado com o usuário.

## 3. Agente e perguntas obrigatórias

- [ ] Escolher framework e provedor/modelo compatíveis com tool calling,
      configuráveis por ambiente; manter o serviço SQL desacoplado do provedor.
- [ ] Proteger a chave em configuração local ignorada pelo Git; nunca expor no
      frontend, logs, exceções públicas ou respostas.
- [ ] Implementar o caminho pergunta -> tool call -> validação -> consulta ->
      interpretação dos dados retornados -> resposta em português.
- [ ] Responder apenas com dados retornados pela consulta; indicar filtros,
      período, unidade e limitações; pedir esclarecimento quando a pergunta não
      determinar uma métrica essencial.
- [ ] Cobrir as perguntas financeiras: top 10 por receita; lucro médio por
      gênero; maiores margens com receita/orçamento válidos.
- [ ] Cobrir popularidade e notas: top 5 populares; divergência TMDB/IMDb;
      média IMDb por ano de lançamento.
- [ ] Cobrir elenco/equipe: ator com mais filmes na janela de cinco anos;
      diretores com maior média e mínimo de cinco filmes; dupla ator-diretor com
      maior número de filmes em comum.
- [ ] Cobrir gênero/produtora: filmes por gênero; maior lucro total por
      produtora; maior margem média por gênero.
- [ ] Cobrir reviews: filmes mais avaliados por usuários; maior divergência entre
      média dos usuários e nota IMDb, respeitando escala e população disponíveis.
- [ ] Criar avaliações locais com perguntas e resultados esperados derivados do
      Gold; comparar números com SQL de referência, não igualdade textual de SQL.
- [ ] Testar ciclo do agente com respostas/tool calls simulados. Reservar
      chamadas reais para uma validação manual pequena: meta máxima de 5 por dia,
      sem retentativas automáticas, anotando o consumo observado.

**Critério de saída:** agente cobre as perguntas obrigatórias, com SQL validado
e sem ultrapassar os controles de uso. Esta etapa depende da conclusão e revisão
do checkpoint da etapa 2.

## 4. Interface e substituição do chatbot anterior

- [ ] Reutilizar o design visual existente para
      apresentar entrada de pergunta, carregamento, resposta, erro e resultados.
- [ ] Integrar o frontend ao serviço GenAI por contrato HTTP explícito, sem
      colocar chave ou chamada direta ao provedor no navegador.
- [ ] Remover a rota/integração Gemini do backend e substituir seu fluxo da
      interface pelo GenAI; manter a apresentação visual reutilizável e demais
      funcionalidades existentes.
- [ ] Validar manualmente um fluxo de pergunta até a apresentação da resposta.

**Critério de saída:** interface permite visualizar pergunta, resposta, estado,
consulta de forma apropriada e resultados tabulares, com o design atual
preservado. Só iniciar após revisar o checkpoint da etapa 3.

## 5. Entrega, operação e pendências da migração anterior

- [ ] Executar `docker compose up --build` e confirmar frontend, aplicação
      existente e dados persistentes em diretório do projeto. A configuração
      está escrita, mas aguarda validação com Docker ativo. Integrar a API GenAI
      só depois da etapa 4.
- [ ] Versionar o Gold real via Git LFS, conferir objeto LFS remoto e documentar
      o checkout completo do arquivo em clones novos.
- [ ] Definir configuração do modelo: chave externa em arquivo local ignorado
      pelo Git ou modelo local iniciado pelo Compose.
- [ ] Atualizar README e tooling para instalação, configuração segura, execução
      independente do módulo, integração visual e exemplos verificados.
- [ ] Confirmar que Gold, segredos, bancos locais e arquivos `.env` não entram
      no Git; executar verificações pertinentes e `git diff --check`.
- [ ] Validar migração em cópia descartável do banco operacional e Gold;
      comparar chaves e valores Gold no operacional e exercitar CRUD/reviews.
      Esta verificação pertence à aplicação preservada e não bloqueia o início do
      módulo GenAI.
- [ ] Publicar no GitHub somente com autorização explícita.

**Critério de saída:** a stack prevista inicia em clone limpo e os critérios
obrigatórios das etapas anteriores estão verificados. A entrega completa
continua pendente enquanto as etapas GenAI não forem concluídas.

## Depois dos requisitos obrigatórios

Avaliar como opcionais, por valor e prazo: gráficos, memória, cache, fallback,
busca semântica para perguntas descritivas, avaliação ampliada e Databricks. Cada
extra precisa de justificativa, limite e verificação própria; nenhum deles
bloqueia a entrega obrigatória.
