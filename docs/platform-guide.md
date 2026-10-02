# Guia rápido da plataforma CineData

Este guia descreve as funções visíveis na interface atual do CineData. O
catálogo pode ser explorado sem entrar; recursos pessoais pedem uma conta.

## Encontrar filmes

A aba **Início** reúne a busca e o catálogo de filmes. Pesquise pelo título,
escolha um gênero ou abra **Filtros
avançados** para filtrar por pessoa (elenco ou direção), produtora, intervalo de
anos, duração e nota mínima. Os resultados podem ser ordenados por relevância,
lançamento mais recente ou título. Selecione um filme para abrir os detalhes.

Na tela de detalhes, você encontra sinopse, gêneros, lançamento, duração,
direção, elenco, roteiro, produtoras, nota e quantidade de avaliações. Quando
disponíveis, também aparecem trailer e números de bilheteria, popularidade e
notas TMDB/IMDb. A seção **O que acharam do filme** mostra avaliações; com uma
conta, você pode publicar ou atualizar a sua. Também é possível salvar o filme
em uma lista própria.

## Recursos da conta

- **Minhas listas:** crie e edite listas, defina cada uma como pública ou
  privada e adicione ou remova filmes. A área também reúne uma lista automática
  de filmes avaliados.
- **Amigos:** pesquise pessoas, envie pedidos de amizade e acompanhe pedidos
  recebidos. Perfis públicos podem mostrar informações e atividades conforme
  suas configurações de visibilidade.
- **Comunidades:** explore comunidades e suas conversas. Para publicar,
  comentar ou reagir, entre na sua conta e participe da comunidade.
- **Mapa de gostos:** depois de avaliar filmes, explore as conexões e sugestões
  formadas a partir deles. O mapa pode ser atualizado e pesquisado pelo título.

Entre ou crie uma conta pelos controles no topo do site para usar listas,
avaliar filmes, gerenciar amizades, participar de conversas e abrir o mapa de
gostos. Algumas ferramentas de gestão — como adicionar, editar ou excluir filmes
e criar ou moderar comunidades — aparecem apenas para administradores.

## Analytics

A aba Analytics é um painel administrativo: o botão aparece apenas para contas
com perfil de administrador. Ela reúne totais de filmes no catálogo, pessoas
cadastradas, avaliações feitas pela comunidade, listas e comunidades. Também
mostra a evolução de cadastros, avaliações, listas e publicações, os gêneros e
filmes mais avaliados pela comunidade e as comunidades em alta. É possível
selecionar 7, 30 ou 90 dias para os gráficos e rankings de atividade; os totais
gerais do topo representam toda a plataforma.

## Chatbot

Na aba Chatbot, faça perguntas sobre os filmes e as métricas do catálogo ou
peça ajuda para encontrar e usar as áreas do CineData. Perguntas sobre dados
dos filmes podem mostrar uma tabela; orientações sobre o site aparecem em
texto. Cada pergunta é independente: para mudar um filtro ou período, inclua-o
na nova pergunta. Se quiser ideias, abra o botão **Ajuda** dentro da conversa.

## Onde conferir

Este resumo foi conferido na navegação e nos componentes do frontend em
`frontend/src/App.tsx`, `frontend/src/pages/Catalog.tsx` e
`frontend/src/components/`, e nas rotas correspondentes em
`backend/app/api/v1/`. As funcionalidades podem mudar; antes de orientar sobre
uma ação específica, confirme que ela continua disponível na interface.
