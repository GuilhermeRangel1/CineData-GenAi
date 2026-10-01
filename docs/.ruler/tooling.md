# Tooling e convenções — CineData GenAI

**Escopo vigente:** o segundo bloco da etapa 2 está concluído. O próximo bloco
deve tratar somente da conexão read-only ao Gold. Não implemente executor SQL,
agente, provedor/modelo, chamadas externas ou integração de interface antes de
o usuário revisar e commitar este checkpoint.

## Separação do módulo

O plano canônico fica em [`TODO.md`](TODO.md). O produto GenAI deve ser
implementado como bloco autônomo, preferencialmente em `genai/`, com API
FastAPI, configuração, dependências, execução e testes próprios. Não importe
rotas, modelos ou dependências do backend social/catálogo para implementar o
agente.

```text
.
├── genai/                 # módulo FastAPI Text-to-SQL (novo foco)
│   ├── app/               # API, agente, ferramenta SQL e acesso SQLite
│   ├── tests/             # testes determinísticos sem chamadas externas
│   └── pyproject.toml     # dependências isoladas do módulo
├── backend/               # aplicação CineData existente; preservada
├── frontend/              # design existente integrado ao serviço GenAI
├── cinerocket.db          # Gold distribuído via Git LFS; somente leitura
├── data/                  # SQLite operacional local, ignorado pelo Git
└── docs/.ruler/            # decisões e plano de progresso
```

O Compose atual prepara os arquivos SQLite para a aplicação existente. O Gold
é montado em modo somente leitura; o banco operacional persiste em `./data`.

## Gold e regras analíticas

- O serviço GenAI consulta diretamente `cinerocket.db` em SQLite read-only.
  Não consulta o banco operacional do app e não depende da sincronização Gold
  para responder às perguntas da atividade.
- Caminho do arquivo configurável por ambiente; falhar com mensagem útil se
  estiver ausente/inválido. Não alterar nem incluir o Gold na imagem.
- O Gold é distribuído via Git LFS. Clones precisam obter o objeto LFS; se o
  serviço receber apenas o arquivo pointer, a inicialização deve explicar como
  buscar o objeto em vez de iniciar silenciosamente sem dados.
- O banco operacional fica em `./data/rocketlab.db`, fora do Git. Na primeira
  subida, o serviço de preparação copia com SQLite backup API o banco do volume
  legado, se existir; mantém intacto o volume original.
- Inspecionar o esquema real antes de escrever SQL, documentar somente as
  colunas/relações necessárias e confirmar amostras e cardinalidades.
- Receita usa a coluna de receita do Gold. Lucro é receita menos orçamento
  quando ambos existem. Margem é lucro dividido pela receita somente quando
  receita > 0. O relatório explicita exclusões por dados ausentes.
- “Últimos cinco anos” usa janela móvel ancorada na data de execução e data de
  lançamento; informar o período aplicado.
- Divergência entre notas usa diferença absoluta somente com escalas
  comprovadamente comparáveis. Se não forem, normalizar com regra explícita e
  validada ou não comparar.
- Agregar fatos por filme antes de combinar dimensões/bridges multivaloradas;
  usar filme distinto nas contagens; desempatar com ordenação estável.
- Usar schema e população reais para separar avaliações de usuários de notas
  externas. A fórmula final deve seguir as perguntas da atividade e ficar no
  TODO/documentação junto de seus filtros e limites.

## API, provedor e segurança

- API FastAPI separada com contrato pequeno de pergunta/resposta/erro; sem
  autenticação, memória ou persistência de conversa no escopo obrigatório.
- Framework de agente e provedor/modelo precisam suportar tool calling e devem
  poder ser trocados sem reescrever a ferramenta SQL.
- Chave e modelo vêm de configuração local/ambiente. Nunca enviar chave ao
  frontend, registrar segredo em logs, ou incluí-lo em erros, README ou Git.
- Modelo só pede a ferramenta tipada; acesso ao arquivo e execução SQL passam
  exclusivamente pelo executor controlado.
- Permitir uma consulta de leitura por chamada, tabelas Gold em allowlist,
  parser/validação compatível com SQLite e conexão `mode=ro`. Recusar DML, DDL,
  múltiplas instruções, `ATTACH`/`DETACH`, extensões e acesso externo.
- Definir limite de tempo e linhas após avaliar as consultas obrigatórias.
  Erros de validação não executam SQL; respostas factuais vêm apenas do
  resultado executado. Não expor caminho privado ou traceback ao cliente.

## Testes e cota diária

- Testes unitários, agregações e fluxo de agente usam SQLite temporário,
  consultas de referência e respostas do provedor simuladas. A suíte normal
  deve fazer **zero chamadas externas**.
- Testar SELECT permitido e bloqueios de escrita, DDL, múltiplas instruções,
  tabelas fora da allowlist, SQL inválido, banco ausente/inválido, timeout,
  limite de linhas e resultado vazio.
- Testar agregações com nulos, joins 1:N, duplicações potenciais, empate e
  escalas/populações de notas, comparando com SQL de referência independente.
- A cota informada é até 50 chamadas diárias no plano gratuito do provedor;
  tool calling pode gastar mais de uma chamada por pergunta. Recomenda-se teto
  operacional de 5 chamadas reais por dia durante desenvolvimento, chamadas
  manuais sem retry em loop e anotação do consumo observado. O teto pode ser
  reduzido se o painel do provedor mostrar limite inferior.
- Não rodar avaliações em lote com o modelo real. Uma rodada curta de smoke
  com perguntas representativas só ocorre depois dos testes locais e do
  orçamento diário ser conferido.

## Execução do banco operacional

- Compose monta `./cinerocket.db` em `/workspace/cinerocket.db` somente para
  leitura e liga `./data` a `/app/data`. A preparação dos dados acontece antes
  da API; um volume Docker legado é preservado e copiado somente quando o banco
  ainda não existe em `./data`.

## Frontend e aplicação existente

- Construir primeiro e validar a API GenAI. Depois integrar o frontend ao
  endpoint FastAPI por HTTP; nunca fazer chamada ao modelo diretamente do
  navegador.
- Reaproveitar o design existente para entrada de pergunta, estado de execução,
  resposta, erro e tabelas/valores retornados. O layout é uma camada de
  apresentação, não parte do agente.
- Substituir/remover o chatbot Gemini somente quando o novo fluxo estiver
  integrado. Preservar o restante do frontend e as funcionalidades antigas.
- Manter a sincronização e os testes da aplicação full-stack separados do
  ciclo de desenvolvimento e dos critérios de conclusão do módulo GenAI.

## Documentação e fluxo de trabalho

- README deve explicar setup isolado do serviço GenAI, caminho do Gold,
  configuração segura, execução, perguntas suportadas, limites e integração
  visual somente quando os comandos estiverem implementados e verificados.
- Atualizar este tooling e o TODO canônico quando uma decisão arquitetural
  mudar; evitar listas detalhadas duplicadas.
- Rodar testes pertinentes ao código alterado e `git diff --check`; distinguir
  comandos executados de comandos apenas documentados.
- Não marcar tarefa como concluída antes de seu critério de saída. Preservar
  mudanças existentes. Não criar commits, publicar ou alterar remotos sem
  solicitação explícita.
