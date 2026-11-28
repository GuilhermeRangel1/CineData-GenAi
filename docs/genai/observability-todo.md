# TODO — Observabilidade do GenAI

O painel interno do CineData deve ajudar a entender quanto o GenAI é usado, quanto custa e onde demora. No chat, cada pessoa pode conferir os detalhes das próprias respostas.

## Proposta de tela para revisão

Abra a [prévia interativa](observability-preview.html) para comparar a proposta com a referência visual. O [contrato de API](observability-api.md) descreve os dados e as permissões de cada visão.

Adicionar **GenAI** dentro da área administrativa **Analytics**, ao lado da visão atual da plataforma. Manter a navegação principal do CineData e usar a própria tela de Analytics como referência para o cabeçalho verde escuro, títulos em Barlow Condensed, margens, superfícies, bordas, cards e botões de período.

| Área | Como ficaria |
| --- | --- |
| Cabeçalho | **Analytics**, com as opções **Plataforma** e **GenAI** e o seletor **7 dias · 30 dias · 90 dias**. Proposta inicial de abrir com 30 dias. |
| Resumo | Cinco cards em desktop. **Perguntas** com o número de chamadas ao modelo no rodapé, **Tempo de resposta** com p50 e p95, **Erros**, **Cache** e **Custo estimado** com a cobertura da estimativa. |
| Evolução | Um painel no estilo do gráfico de atividade existente, com volume diário de perguntas e alternância para latência p95 ou custo estimado. Cada visão tem unidade própria e os valores podem ser lidos sem depender do gráfico. |
| Uso por modelo | Tabela com provedor, modelo, número de chamadas, tokens de entrada e saída e custo estimado. |
| Histórico | Filtros de rota, provedor, modelo e status acima de uma lista paginada, com as mais recentes primeiro. Cada linha mostra data e hora, ID, rota, status, duração, custo e a ação **Ver detalhes**. O seletor de período vale para toda a visão. |
| Detalhe | Ao abrir uma linha, um diálogo no padrão do CineData mostra duração total, tempos por etapa, chamadas e fallbacks. Quando houver SQL, exibe as seções **SQL gerado** e **SQL executado**, com acesso ao conteúdo integral permitido e ao número de linhas. |

Em telas estreitas, seguir a grade responsiva dos cards de Analytics e apresentar o histórico em linhas empilhadas, com status, tempo e ação de detalhe sempre visíveis. Limitar qualquer rolagem horizontal do SQL ao bloco de código.

Referências no projeto: [AnalyticsDashboard](../../frontend/src/components/AnalyticsDashboard.tsx), [estilos da área Analytics](../../frontend/src/App.css#L2490), [Dialog](../../frontend/src/components/Dialog.tsx) e [ChatbotHub](../../frontend/src/components/ChatbotHub.tsx).

## 1. Registrar as etapas de cada pergunta

- [ ] Criar um ID por pergunta e usá-lo nos registros da API, do modelo e do banco.
- [ ] Aproveitar os registros de rota e tempos existentes. Medir duração total, geração da consulta, execução no Gold e montagem da resposta, conforme a rota.
- [ ] Registrar rota, acerto de cache, SQL gerado, SQL executado, número de linhas retornadas e status final, quando aplicável.
- [ ] Registrar cada tentativa de chamada ao modelo com provedor, modelo, duração, resultado e tokens de entrada e saída reportados. Vincular fallbacks à pergunta original.
- [ ] Estimar o custo de cada chamada com a tarifa aplicável ao modelo. Marcar estimativas sem consumo ou tarifa como indisponíveis e registrar custo de modelo zero para perguntas atendidas sem chamadas.
- [ ] Definir acesso e retenção dos registros. Omitir prompts completos, segredos e dados sensíveis por padrão e revisar o SQL registrado quanto a literais sensíveis.
- [ ] Definir o armazenamento da telemetria fora do banco Gold e preservar a independência do serviço GenAI em relação ao banco social.
- [ ] Cobrir a pergunta via resposta comum e streaming, com um status final por ID, inclusive em timeout ou cancelamento. Garantir que falhas de telemetria preservem o funcionamento do chat.

## 2. Montar o painel administrativo

### 2.1. Revisar a proposta visual

- [ ] Montar um protótipo com dados de exemplo e revisar lado a lado com o Analytics existente, em desktop e celular. Mostrar o histórico, o detalhe aberto e uma consulta com fallback ou custo indisponível.
- [ ] Validar tipografia, largura do conteúdo, espaçamento, hierarquia de títulos e densidade dos dados. Reaproveitar o contêiner, os botões, os ícones e o diálogo existentes onde couber.
- [ ] Aprovar a entrada **Analytics → GenAI**, a ordem das seções e o comportamento do detalhe antes de implementar a tela.

### 2.2. Entregar o histórico e o detalhe

- [ ] Restringir a visão na interface e proteger histórico, detalhe e agregados na API. Usar a autorização administrativa existente em `get_current_admin` como referência e definir como o backend acessará os dados do serviço GenAI.
- [ ] Incluir filtros por período, rota, provedor, modelo e status, com ordenação por mais recentes e paginação na API. Voltar à primeira página ao mudar filtros.
- [ ] Abrir o detalhe via botão **Ver detalhes**. Manter filtros e posição ao fechar. Usar foco visível, navegação por teclado, Escape e retorno do foco ao botão que abriu o diálogo.
- [ ] Exibir tempos por etapa, SQL gerado e executado, linhas retornadas, tentativas e custo por chamada. Explicar etapas ausentes com rótulos como **Servido do cache**, **Sem etapa SQL** ou **Custo indisponível**, conforme o caso.
- [ ] Cobrir carregamento, ausência de registros, filtros sem resultado, erro com nova tentativa e sessão expirada. Cancelar buscas antigas para impedir que trocas rápidas de filtro exibam dados do período anterior.

### 2.3. Entregar o resumo de uso e gastos

- [ ] Exibir perguntas e chamadas ao modelo separadamente, duração p50 e p95, taxa de erros e taxa de acerto do cache. Documentar o denominador de cada taxa, o recorte de tempo e a base usada para os percentis.
- [ ] Exibir evolução diária e consumo por modelo, com o mesmo período do histórico. Formatar datas, números e moeda em português, identificando a moeda da estimativa.
- [ ] Mostrar a cobertura do custo junto ao valor, por exemplo **42 de 50 chamadas com custo estimado**. Prever estados distintos para período sem registros, custo parcial e custo indisponível.
- [ ] Usar texto junto às cores de status, manter contraste e foco visível e oferecer uma leitura textual dos valores do gráfico.

## 3. Mostrar detalhes no chat

- [ ] Adicionar **Detalhes da resposta** com duração total, fontes e filtros aplicados, quando disponíveis.
- [ ] Oferecer **Ver SQL executado** em uma seção recolhida quando a consulta usar dados do catálogo que a pessoa possa inspecionar.
- [ ] Validar na API que cada pessoa só acesse detalhes das próprias respostas. Reservar tokens e custos ao painel admin.

## 4. Validar os fluxos

- [ ] Cobrir perguntas atendidas pelo modelo, pelo cache e por rotas sem IA. Exercitar fallback, erro e timeout com mocks.
- [ ] Conferir que um fallback conta como uma pergunta com múltiplas tentativas e que um acerto de cache acrescenta zero chamadas ao modelo.
- [ ] Verificar que uma chamada com custo indisponível mantém esse status nos totais e que o painel informa a cobertura da estimativa.
- [ ] Verificar que usuários comuns recebem acesso negado ao painel e aos seus endpoints, e que a API recusa detalhes de respostas de outra pessoa.
- [ ] Verificar que a tela atual de Analytics continua acessível, que sair da sessão fecha qualquer detalhe admin e que uma mudança rápida de período ou filtro mantém tabela e indicadores coerentes.
- [ ] Conferir desktop e celular com SQL longo, modelos com nomes extensos e estados de carregamento, vazio e falha. Percorrer filtros, histórico e detalhe usando só teclado.

O primeiro bloco de implementação é o registro das etapas no backend. Em paralelo à discussão desse contrato, revisar a proposta visual com dados de exemplo. A primeira entrega utilizável pelo admin inclui o histórico e o detalhe. O resumo de uso e gastos e os detalhes no chat reaproveitam esse registro em entregas seguintes.
