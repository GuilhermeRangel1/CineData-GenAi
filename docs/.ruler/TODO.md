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

**Critério de saída:** a aplicação completa inicia conforme as instruções de
clone e mantém as funcionalidades anteriores; documentação e arquivos
versionados correspondem ao estado entregue.

## 6. Responder sobre o CineData (extra prioritário)

- [x] Criar um guia curto e versionado das funcionalidades reais do site:
      Início, catálogo e detalhes dos filmes; busca e filtros por gênero, pessoa,
      produtora, ano, duração e nota; listas, avaliações, amigos, comunidades,
      mapa de gostos, Analytics, Chatbot e áreas restritas por perfil. Conferido
      no frontend e nas rotas; ver [`platform-guide.md`](../platform-guide.md).
- [x] Encaminhar perguntas sobre **como usar o CineData** para esse guia, sem
      gerar SQL analítico nem inventar funções. Separar esse caminho das
      perguntas sobre dados dos filmes; pedidos mistos identificam separadamente
      o guia da plataforma e os resultados Gold. O contrato registra a origem.
- [x] Explicar requisitos de acesso quando relevantes, como entrar na conta
      para usar recursos pessoais. Se a funcionalidade não existir ou a pergunta
      estiver vaga, dizer isso com clareza e pedir o detalhe necessário. As
      respostas da plataforma incluem o requisito pertinente; funções não
      documentadas são indicadas como tal e pedidos vagos recebem esclarecimento.
- [x] Cobrir o roteamento e o conteúdo do guia com verificações locais sem
      provedor; conferir manualmente uma pergunta de cada tipo. Os cinco fluxos
      (plataforma, analítico, misto, vago e não documentado) passaram no container
      isolado sem rede; plataforma também foi consultada sem modelo, e os casos
      analítico e misto foram enviados uma vez ao Gemini. A suíte pytest foi
      adicionada, mas não executada neste host porque pytest não está instalado.

**Critério de saída:** a pessoa consegue perguntar o que pode fazer no site e
como encontrar filmes, listas, amigos ou comunidades; o chatbot responde com
informação verificada da plataforma, sem tentar gerar SQL para esse tema.

## 7. Botão Ajuda com perguntas sugeridas

- [x] Adicionar um botão **Ajuda** dentro do chat com exemplos curtos e
      clicáveis sobre catálogo, métricas e uso da plataforma.
- [x] Manter os exemplos sincronizados com as perguntas que o chatbot consegue
      responder; abrir e fechar a ajuda não chama o modelo. As perguntas sobre
      o site foram conferidas pelo endpoint sem chamadas ao provedor; as duas
      perguntas analíticas já estão no fluxo obrigatório do módulo.

**Critério de saída:** a pessoa encontra uma sugestão e consegue enviá-la no
chat; os exemplos não expõem tabelas, chaves ou detalhes de implementação.

## Extras independentes

As etapas abaixo podem ser priorizadas conforme benefício e prazo; nenhuma
bloqueia a entrega obrigatória. A interface visual já está na etapa 4, os
guardrails básicos de SQL na etapa 2 e a avaliação local das 14 perguntas na
etapa 3. Cada extra amplia uma dessas capacidades. Planejar checkpoints dentro
de cada etapa e manter as chamadas reais dentro do orçamento diário.

## 8. Guardrails adicionais

- [x] Identificar perguntas adversariais, tentativas de consultar outras fontes
      e padrões de SQL excessivamente custosos, além dos bloqueios já existentes.
- [x] Melhorar a rejeição e as mensagens de erro sem impedir consultas legítimas
      do catálogo; usar exemplos locais para avaliar falsos bloqueios.

**Critério de saída atendido:** entradas que pedem instruções do sistema, SQL
direto ou fontes externas são rejeitadas antes do provedor. O guard SQL também
limita estruturas caras e funções inadequadas. Casos adversariais, consultas
legítimas e o contrato HTTP foram verificados localmente sem chamadas ao
provedor.

## 9. Gráficos para respostas analíticas

- [x] Identificar resultados que se beneficiam de gráfico, como médias por ano,
      rankings e comparações entre gêneros.
- [x] Renderizar o gráfico a partir das linhas retornadas pela API, com título,
      unidade e escala adequados; preservar a tabela acessível como alternativa.
- [x] Criar um agente de insights separado da ferramenta SQL, que receba apenas
      os dados retornados, a métrica, a unidade e o período para destacar até
      três achados objetivos sem inventar números nem consultar o Gold.
- [x] Exibir os insights junto do gráfico e incluí-los no contrato da resposta,
      preparando o armazenamento no mesmo cache quando a etapa de cache for
      implementada.

**Critério de saída:** respostas adequadas mostram um gráfico legível, com os
mesmos valores da tabela e insights fiéis aos dados; respostas inadequadas
continuam apenas em tabela.

## 10. Memória de conversa

- [x] Definir o contexto mínimo para perguntas de continuação, como “e em
      2020?”, sem mudar silenciosamente a métrica ou os filtros anteriores.
- [x] Limitar e permitir limpar o histórico; separar sessões e não incluir
      segredos ou dados pessoais desnecessários no contexto enviado ao modelo.

**Critério de saída:** uma pergunta de continuação usa o contexto correto, uma
conversa nova não herda esse contexto e a pessoa consegue apagá-lo.

## 11. Fallback entre modelos gratuitos

- [x] Configurar um modelo alternativo e definir quais falhas permitem a troca,
      considerando disponibilidade, cota diária e tempo total de resposta.
- [x] Registrar qual modelo respondeu sem expor chaves; evitar novas tentativas
      quando a falha estiver na pergunta, na validação ou no banco.

**Critério de saída:** a troca ocorre apenas nas falhas previstas, mantém o
mesmo contrato de resposta e não cria uma sequência ilimitada de chamadas.

## 12. Cache de respostas

- [x] Definir uma chave que considere pergunta, filtros, contexto aplicável e
      versão do Gold, sem misturar respostas de sessões diferentes.
- [x] Estabelecer expiração e invalidação quando os dados ou as regras mudarem;
      deixar claro quando uma resposta veio do cache.

**Critério de saída:** perguntas equivalentes evitam trabalho repetido e uma
atualização do Gold ou mudança de contexto não devolve dados antigos.

## 13. Avaliação ampliada

- [ ] Ampliar os casos Q01–Q14 com variações de linguagem, filtros, empates,
      ambiguidades, resultados vazios e perguntas sobre a plataforma.
- [ ] Comparar números e regras com consultas de referência; medir também
      cobertura, erros e tempo sem exigir SQL textual idêntico.

**Critério de saída:** a avaliação detecta respostas incorretas e regressões
com dados locais e mocks; chamadas reais permanecem manuais e reduzidas.

## 14. Agente híbrido SQL e busca semântica

- [ ] Preparar um índice das sinopses e de outros textos autorizados, com forma
      de atualizar o índice quando o catálogo mudar.
- [ ] Encaminhar perguntas descritivas para busca semântica e quantitativas
      para SQL; combinar evidências quando a pergunta exigir as duas fontes.

**Critério de saída:** respostas descritivas apontam os filmes encontrados,
números vêm de SQL e a origem de cada informação fica clara para a pessoa.

## 15. Privacidade e conversa temporária

- [ ] Adicionar um modo de conversa temporária que mantenha o contexto apenas
      durante a sessão aberta e permita apagar a conversa a qualquer momento.
- [ ] Evitar que dados pessoais, tokens ou identificadores da conta sejam
      enviados ao modelo; anonimizar ou remover esses dados quando forem
      necessários para uma resposta.
- [ ] Informar de forma simples quando a conversa temporária estiver ativa e
      quais dados são usados para responder.

**Critério de saída:** a pessoa pode iniciar uma conversa temporária, encerrar
e limpar seu contexto sem persistência indevida; o modelo recebe somente os
dados necessários e nenhum segredo ou identificador pessoal.
