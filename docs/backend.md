# Convenção da API

Este documento registra como o frontend conversa com o backend. Ele existe para
que ambos usem as mesmas rotas, parâmetros e formatos de resposta.

## Prefixo `/api/v1`

O projeto-base já define `/api/v1` como prefixo das rotas de negócio. O `v1`
significa apenas a primeira versão da API; não acrescenta nenhuma funcionalidade
à atividade. Todas as rotas abaixo seguem esse prefixo.

## Regras gerais

- As rotas usam JSON e nomes de campos em português.
- O ID público de um filme é `id`; chaves internas, como `sk_movie_id`, não são
  expostas.
- Notas e médias usam a escala de 0 a 10.
- Coleções usam paginação e ordenação estável.
- Erros não expõem SQL, exceções ou caminhos locais.
- Rotas autenticadas recebem `Authorization: Bearer <jwt>`.

## Rotas disponíveis

| Método | Rota | Finalidade | Acesso |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/cadastro` | Cria conta de usuário | Público |
| `POST` | `/api/v1/auth/login` | Inicia sessão e devolve JWT | Público |
| `GET` | `/api/v1/auth/perfil` | Consulta perfil completo da própria conta | Autenticado |
| `PATCH` | `/api/v1/auth/perfil` | Atualiza nome e/ou avatar | Autenticado |
| `GET` | `/api/v1/perfis/{usuario_id}` | Consulta perfil público | Público |
| `GET` | `/api/v1/filmes` | Catálogo, busca, filtros e paginação | Público |
| `POST` | `/api/v1/filmes` | Cadastra filme | `admin` |
| `GET` | `/api/v1/filmes/{filme_id}` | Consulta detalhes de filme | Público |
| `PATCH` | `/api/v1/filmes/{filme_id}` | Atualiza filme | `admin` |
| `DELETE` | `/api/v1/filmes/{filme_id}` | Remove filme | `admin` |
| `GET` | `/api/v1/filmes/{filme_id}/avaliacoes` | Lista avaliações públicas do filme | Público |
| `GET` | `/api/v1/filmes/{filme_id}/minha-avaliacao` | Consulta avaliação da conta atual | Autenticado |
| `POST` | `/api/v1/filmes/{filme_id}/avaliacoes` | Cria ou atualiza avaliação da conta atual | Autenticado |
| `DELETE` | `/api/v1/filmes/{filme_id}/minha-avaliacao` | Remove avaliação da conta atual | Autenticado |
| `GET` | `/api/v1/filmes/{filme_id}/trailer` | Consulta trailer disponível | Público |
| `GET` | `/api/v1/minha-conta/listas` | Lista coleções da conta atual | Autenticado |
| `POST` | `/api/v1/minha-conta/listas` | Cria lista | Autenticado |
| `GET` | `/api/v1/minha-conta/listas/{lista_id}` | Consulta lista e seus filmes | Autenticado (dona) |
| `PATCH` | `/api/v1/minha-conta/listas/{lista_id}` | Atualiza lista | Autenticado (dona) |
| `DELETE` | `/api/v1/minha-conta/listas/{lista_id}` | Remove lista | Autenticado (dona) |
| `POST` | `/api/v1/minha-conta/listas/{lista_id}/filmes/{filme_id}` | Adiciona filme à lista | Autenticado (dona) |
| `DELETE` | `/api/v1/minha-conta/listas/{lista_id}/filmes/{filme_id}` | Remove filme da lista | Autenticado (dona) |
| `GET` | `/api/v1/minha-conta/assistir-depois` | Lista filmes salvos para assistir depois | Autenticado |
| `PUT` | `/api/v1/minha-conta/assistir-depois/{filme_id}` | Salva filme para assistir depois | Autenticado |
| `DELETE` | `/api/v1/minha-conta/assistir-depois/{filme_id}` | Remove filme de assistir depois | Autenticado |
| `GET` | `/api/v1/minha-conta/filmes-avaliados` | Lista filmes avaliados pela conta | Autenticado |
| `GET` | `/api/v1/minha-conta/conversas` | Lista conversas salvas da conta | Autenticado |
| `POST` | `/api/v1/minha-conta/conversas` | Cria conversa salva | Autenticado |
| `GET` | `/api/v1/minha-conta/conversas/{conversa_id}` | Retoma conversa e mensagens | Autenticado (dona) |
| `PATCH` | `/api/v1/minha-conta/conversas/{conversa_id}` | Renomeia conversa | Autenticado (dona) |
| `DELETE` | `/api/v1/minha-conta/conversas/{conversa_id}` | Exclui conversa | Autenticado (dona) |
| `POST` | `/api/v1/minha-conta/conversas/{conversa_id}/mensagens` | Salva mensagens exibidas no chat | Autenticado (dona) |
| `GET` | `/api/v1/minha-conta/amigos` | Lista amizades aceitas | Autenticado |
| `GET` | `/api/v1/minha-conta/amigos/solicitacoes` | Lista pedidos enviados e recebidos | Autenticado |
| `GET` | `/api/v1/minha-conta/amigos/pesquisa` | Pesquisa pessoas para conexão | Autenticado |
| `POST` | `/api/v1/minha-conta/amigos/solicitacoes/{usuario_id}` | Envia pedido de amizade | Autenticado |
| `PATCH` | `/api/v1/minha-conta/amigos/solicitacoes/{solicitacao_id}` | Responde a pedido de amizade | Autenticado (destinatária) |
| `DELETE` | `/api/v1/minha-conta/amigos/{usuario_id}` | Remove amizade | Autenticado |
| `GET` | `/api/v1/comunidades` | Lista comunidades | Público |
| `POST` | `/api/v1/comunidades` | Cria comunidade | `admin` |
| `GET` | `/api/v1/comunidades/{comunidade_id}` | Consulta comunidade | Público |
| `PATCH` | `/api/v1/comunidades/{comunidade_id}` | Atualiza comunidade | `admin` |
| `DELETE` | `/api/v1/comunidades/{comunidade_id}` | Remove comunidade | `admin` |
| `POST` | `/api/v1/comunidades/{comunidade_id}/visualizacoes` | Registra abertura da comunidade | Público |
| `GET` | `/api/v1/comunidades/{comunidade_id}/membros` | Lista participantes | Público |
| `POST` | `/api/v1/comunidades/{comunidade_id}/participacao` | Participa da comunidade | Autenticado |
| `DELETE` | `/api/v1/comunidades/{comunidade_id}/participacao` | Sai da comunidade | Autenticado |
| `GET` | `/api/v1/comunidades/{comunidade_id}/publicacoes` | Lista publicações e conversa | Público |
| `POST` | `/api/v1/comunidades/{comunidade_id}/publicacoes` | Publica na comunidade | Autenticado (membro) |
| `POST` | `/api/v1/comunidades/publicacoes/{publicacao_id}/comentarios` | Comenta em publicação | Autenticado (membro) |
| `DELETE` | `/api/v1/comunidades/publicacoes/{publicacao_id}` | Modera publicação | `admin` |
| `DELETE` | `/api/v1/comunidades/comentarios/{comentario_id}` | Modera comentário | `admin` |
| `POST` | `/api/v1/comunidades/publicacoes/{publicacao_id}/reacoes` | Cria ou atualiza reação | Autenticado (membro) |
| `DELETE` | `/api/v1/comunidades/publicacoes/{publicacao_id}/reacoes` | Remove reação da conta atual | Autenticado |
| `GET` | `/api/v1/mapa-de-gostos` | Consulta recomendações e grafo pessoal | Autenticado |
| `GET` | `/api/v1/admin/analytics/resumo` | Consulta indicadores agregados | `admin` |
| `GET` | `/api/v1/admin/fontes/tmdb/busca` | Pesquisa títulos no TMDB | `admin` |
| `GET` | `/api/v1/admin/fontes/tmdb/{tmdb_id}` | Consulta detalhes para importação do TMDB | `admin` |
| `POST` | `/api/v1/auth/sessao-teste` | Inicia sessão da conta demo do Compose | Somente Compose; oculta da OpenAPI |

As rotas são mantidas em `backend/app/api/v1/`; a documentação interativa fica
em `/docs` durante a execução local. A sessão de teste do Compose é a única rota
intencionalmente oculta da OpenAPI.

### Contas e sessão

`POST /api/v1/auth/cadastro` recebe `nome`, `email` e `senha`; a conta sempre
nasce com o papel `user`. `POST /api/v1/auth/login` recebe `email` e `senha` e
devolve o JWT Bearer e os dados públicos da conta. O único `admin` inicial é
criado pelo comando de bootstrap da infraestrutura, nunca pelo cadastro público.

### Catálogo

`GET /api/v1/filmes` aceita parâmetros combináveis:

| Parâmetro | Padrão | Regra |
| --- | --- | --- |
| `busca` | - | Busca no título, sem diferenciar maiúsculas e minúsculas. |
| `genero` | - | Filtra pelo nome do gênero. |
| `pessoa` | - | Filtra por pessoa associada ao filme. |
| `produtora` | - | Filtra por produtora. |
| `ano_inicial`, `ano_final` | - | Limites inclusivos do ano de lançamento. |
| `duracao_minima`, `duracao_maxima` | - | Limites inclusivos em minutos. |
| `nota_minima` | - | Nota externa mínima disponível. |
| `pagina` | `1` | Mínimo `1`. |
| `tamanho_pagina` | `12` | Entre `1` e `100`. |
| `ordenar_por` | `relevancia` | Aceita `relevancia`, `titulo` ou `ano_lancamento`. Relevância ajusta a nota TMDB pelo volume de votos e usa popularidade como desempate. |
| `direcao` | `asc` | Aceita `asc` ou `desc`; aplicada aos modos `titulo` e `ano_lancamento`. |
| `priorizar_capa`, `priorizar_trailer`, `somente_com_trailer` | `false` | Ordena por mídia disponível ou restringe a filmes com trailer. |

Em empates, a API ordena por título e ID. Isso evita que itens mudem de página
entre duas consultas iguais.

Exemplo:

```text
GET /api/v1/filmes?busca=vida&genero=Drama&pagina=2&tamanho_pagina=12&ordenar_por=ano_lancamento&direcao=desc
```

Resposta paginada:

```json
{
  "itens": [],
  "meta": {
    "pagina": 1,
    "tamanho_pagina": 12,
    "total_itens": 0,
    "total_paginas": 0
  }
}
```

### Avaliações

`POST /api/v1/filmes/{filme_id}/avaliacoes` recebe `nota`, `comentario` e, se
desejado, `visibilidade`; exige uma sessão válida. A nota aceita qualquer valor
numérico entre `0` e `10`, inclusive. A conta pode ter no máximo uma avaliação
por filme: a primeira gravação retorna `201 Created`; novas chamadas atualizam
a mesma avaliação e retornam `200 OK`. O banco aplica uma restrição única para
proteger também envios simultâneos. A operação atualiza quantidade e média do
filme; avaliações importadas sem conta permanecem separadas.

`GET /api/v1/filmes/{filme_id}/avaliacoes` retorna o histórico disponível, da
avaliação mais recente para a mais antiga. Ambas as rotas retornam `404` quando
o filme não existe.

`GET /api/v1/filmes/{filme_id}/minha-avaliacao` retorna a avaliação privada ou
pública da conta autenticada. `DELETE` no mesmo caminho apaga somente a
avaliação da conta e recompõe o resumo do filme.

### Listas, conversas, comunidades e descoberta

As rotas sob `/api/v1/minha-conta/listas` e `/assistir-depois` só expõem dados da
conta autenticada. O perfil público contém apenas avaliações e listas públicas;
`GET /api/v1/auth/perfil` permite ao dono ver também os próprios itens privados.

As rotas sob `/api/v1/minha-conta/conversas` mantêm o histórico privado do
chatbot. Cada conversa pertence a uma única conta; os registros armazenam título,
datas, papel e conteúdo das mensagens, além da resposta estruturada quando ela
existir. Conversas temporárias não chamam essas rotas e não são persistidas.

As operações de comunidade que alteram a conversa exigem participação; a
criação, edição e remoção de comunidades exige `admin`. Administradores também
podem moderar conteúdo individual com `DELETE /api/v1/comunidades/publicacoes/{id}`
ou `DELETE /api/v1/comunidades/comentarios/{id}`. Esses endpoints limpam o texto
e devolvem `204`; as leituras seguintes marcam o item com
`removida_por_moderacao: true` e não expõem o texto original. Moderar uma
publicação redige seus comentários, remove a menção a filme e suas reações.
Publicações moderadas não aceitam novas respostas ou reações (`409`). O painel em
`/api/v1/admin/analytics/resumo?periodo_dias=30` agrega atividade e rankings, com
um intervalo configurável de 1 a 90 dias. O mapa aceita `limite_nos` (6 a 48),
`vizinhos_por_filme` (1 a 6), `busca` e parâmetros repetidos `excluir` para
renovar sugestões sem repetir os nós recomendados da rodada anterior.

`/api/v1/admin/fontes/tmdb` é protegido por papel `admin`; o token TMDB é lido
somente pelo backend e nunca faz parte da resposta ao navegador.

## Erros

| Situação | Status |
| --- | --- |
| Dados inválidos, como `pagina=0` | `422 Unprocessable Entity` |
| Token ausente ou inválido | `401 Unauthorized` |
| Conta sem o papel exigido | `403 Forbidden` |
| Filme inexistente | `404 Not Found` |
| Conflito de estado | `409 Conflict` |
| Falha inesperada | `500 Internal Server Error` |

Quando houver erro controlado, a resposta usa este formato:

```json
{
  "codigo": "REQUISICAO_INVALIDA",
  "mensagem": "Dados da requisição são inválidos."
}
```

Erros de domínio seguem o mesmo formato. Por exemplo, uma consulta a um filme
inexistente retorna `404` com `FILME_NAO_ENCONTRADO`.
