# Interface e mídia

O frontend usa React, TypeScript e CSS, com componentes separados para destaque,
fileiras, cards, catálogo e detalhes. O cliente HTTP fica em
`frontend/src/api/client.ts`, usando `VITE_API_BASE_URL`
(padrão: `http://localhost:8000/api/v1`).

## Fluxos disponíveis

- Catálogo real com busca por título, filtro por gênero, ordenação e paginação.
- Fileiras de animação e aventura, também consultadas na API.
- Detalhes em `dialog` nativo: sinopse, pessoas, produtoras, desempenho, média
  e histórico. Escape fecha a janela e devolve o foco.
- Estados de carregamento, vazio, erro e nova tentativa. Buscas antigas são
  canceladas para evitar que uma resposta atrasada substitua a atual.
- Pôsteres ausentes ou quebrados recebem uma apresentação com o título.
- O catálogo prioriza filmes com pôster ou backdrop, sem omitir registros sem
  imagem. Quando um pôster não existe, o card usa o backdrop como alternativa;
  nos detalhes, o pôster também substitui um backdrop ausente.
- Respostas de catálogo e detalhes são mantidas por até um minuto no cache em
  memória do cliente. Qualquer cadastro, edição, exclusão ou avaliação limpa
  esse cache antes de as consultas serem atualizadas, evitando dados obsoletos.
- Cadastro, login e encerramento de sessão locais pelo cabeçalho. A sessão JWT
  é mantida no navegador e enviada nas escritas da API.
- Perfil próprio editável com avatar, além de perfis públicos com avaliações
  recentes, listas públicas, comunidades e contagem de amizades. Perfis públicos
  mostram até seis filmes de cada lista como prévia; clicar no nome abre a lista
  completa em um pop-up. No perfil de outra pessoa, também é possível enviar um
  pedido de amizade.
- A navegação principal dá acesso a **Minhas listas**. Contas autenticadas podem
  criar, editar e apagar listas pessoais, definir sua visibilidade e ver os
  filmes como cards com capa. Pelo detalhe de qualquer filme do catálogo, a
  pessoa escolhe diretamente em qual lista pessoal quer salvá-lo; a área de
  listas também permite buscar e remover filmes. Filmes avaliados aparecem como
  uma coleção automática visual, sem obrigar o uso de uma lista "assistir depois".
- O botão **Adicionar filme**, a edição e a exclusão ficam visíveis apenas para
  administradores. O formulário oferece título, diretor, ano, gêneros, sinopse,
  data completa e links opcionais de imagens.
- Edição via PATCH envia apenas campos alterados. Elenco, produtoras e demais
  relações não editadas são preservados. Se houver vários diretores, a interface
  avisa que alterar esse campo substitui a direção pelo único nome informado.
- Exclusão exige confirmação e informa que avaliações também serão removidas.
- Avaliação com a identidade da conta, nota digitável em qualquer valor decimal
  de 0 a 10 e resenha. A pessoa pode editar ou apagar a própria avaliação. Sem
  sessão, a interface convida a entrar. Catálogo, listas, histórico e média são
  consultados novamente após escritas.
- **Amigos** permite pesquisar contas, enviar e responder solicitações, remover
  amizades e abrir perfis. A página mostra pedidos recebidos, busca e amigos,
  com três itens iniciais e acesso para expandir cada coleção. Pedidos enviados
  continuam disponíveis pela API, mas não aparecem nessa página.
- **Comunidades** reúne descoberta, entrada e saída, publicações, comentários,
  menções de filmes e reações visuais 🔥, ❤️, 🍿 e 👎. A conversa atualiza por
  polling enquanto está aberta e visível. Administradores mantêm comunidades e
  podem remover publicações ou comentários individuais após confirmação. O
  conteúdo some e um aviso de moderação ocupa seu lugar, sem apagar o restante
  da conversa.
- **Analytics** é restrito a administradores e consulta agregados do banco para
  atividade recente, gêneros avaliados, filmes e comunidades em alta.
- **Mapa de gostos** é pessoal e exige login. O backend seleciona candidatos
  por gêneros, pessoas e termos de sinopse, calcula similaridade com os demais
  sinais do catálogo e devolve uma malha pequena, explicável e atualizável.
- O cadastro administrativo pode buscar detalhes, imagens e trailer no TMDB;
  a credencial fica no backend. O trailer da home usa o iframe oficial do
  YouTube e depende das regras de reprodução do navegador.
- Campos inválidos recebem mensagens; falhas de escrita preservam o formulário.
  Durante o envio, controles e fechamento da janela ficam bloqueados para
  evitar requisições duplicadas. Uma falha de atualização posterior não é
  apresentada como falha de gravação de uma avaliação já confirmada pela API.

Os dados brutos preservam títulos e gêneros do arquivo original, inclusive
idiomas, datas futuras, notas e imagens indisponíveis. As categorias em português
na interface mapeiam os gêneros em inglês, sem modificar os registros.

O formulário e suas conversões/validações estão separados em `MovieForm` e
`lib/movieForm.ts`. `useMutation` coordena bloqueio de envio e erros; `useResource`
invalida consultas após alterações, preservando filtros e ordenação do catálogo.
Ao remover o último item de uma página, a navegação retorna à última página válida.
Dados são persistidos pela API, não em armazenamento local do navegador.

## Chatbot

A aba **Ajuda** oferece 47 das 50 perguntas oficiais, organizadas por tema.
As três continuações Q47–Q49 fazem parte da bateria de avaliação e usam o
contexto de uma pergunta anterior. O chat pode enviar até dez resumos da
conversa atual ao serviço GenAI.

Conforme o resultado, a interface exibe texto, tabela, gráfico e insights.
Resultados tabulares podem ser exportados em CSV e gráficos em PNG.
O cliente usa `VITE_GENAI_API_BASE_URL`, com padrão `/genai/api/v1`.
Veja o [contrato HTTP](genai/api-contract.md) e o
[catálogo de avaliação](genai/evaluation-cases.md).

## Destaque editorial

Spider-Man: Across the Spider-Verse aparece como seleção editorial e também faz
parte do catálogo local. O botão Explorar animações abre o filtro correspondente
no catálogo.

- Trailer: [Sony Pictures, trailer oficial](https://www.youtube.com/watch?v=shW9i6k8cB0).
- Imagem: miniatura do vídeo oficial, servida pelo YouTube.
- Créditos: © 2023 Sony Pictures Animation.
- Fontes: Manrope e Barlow Condensed, servidas pelo Google Fonts, com
  alternativas locais em CSS.

O trailer usa a API oficial de iframe do YouTube e o domínio
`youtube-nocookie.com`; nenhum vídeo foi baixado ou versionado. Na home, o vídeo
começa automaticamente sem som, entra em loop e pausa quando o destaque sai da
área visível ou quando outra página está ativa. O controle de som aparece quando
a reprodução começa; enquanto o vídeo carrega, a interface mostra
“Carregando trailer”. Com preferência por movimento reduzido, o destaque começa
estático.

A imagem permanece até o evento de reprodução. Bloqueio de autoplay, falha do
player ou tempo excedido mantêm a alternativa estática. Reprodução, imagens e
fontes dependem dos serviços externos e da conexão; bloqueadores ou restrições
do navegador podem impedir o vídeo.

## Verificações

Execute em `frontend/`: `npm run lint`, `npm run test` e `npm run build`.
Os testes com Vitest e Testing Library cobrem catálogo, filtros, paginação,
buscas fora de ordem, erros e nova tentativa, detalhes, pôster indisponível,
player, autenticação, listas, amizades, perfis, comunidades (incluindo
moderação administrativa), analytics e mapa de
gostos. Também cobrem formulários, validações, prevenção de envios duplicados,
preservação de texto em falhas e atualização de dados após alterações. Os testes
usam respostas HTTP simuladas; o backend possui testes de integração próprios.

A interface foi inspecionada no navegador em desktop e áreas de 390 e 320 pixels,
incluindo formulários, confirmação, foco inicial e retorno por Escape. Cadastro,
edição e envio de avaliação foram executados com a API real sobre banco isolado
criado pelo Alembic; média e histórico foram conferidos. A limpeza desse registro
pela API retornou 204, e sua ausência gerou a mensagem de 404 esperada na interface.
A execução do botão de exclusão é coberta no teste integrado do frontend;
a confirmação visual foi inspecionada sem remover registros da base importada.
O trailer oficial, no fundo e na janela própria, já havia sido verificado no
checkpoint visual.
