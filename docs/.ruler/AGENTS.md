# CineData GenAI - instruções do projeto

**Escopo vigente:** o segundo bloco da etapa 3 do plano GenAI está concluído.
O próximo bloco deve tratar somente de uma validação manual curta do adaptador
Gemini e do fluxo de uma pergunta representativa. Não integre frontend, faça
avaliação em lote ou ultrapasse o orçamento de chamadas antes de um novo
checkpoint revisado pelo usuário.

## Processo obrigatório de trabalho em checkpoints

- Divida cada etapa em blocos pequenos, independentes e revisáveis, com um
  resultado claro por bloco.
- Antes de começar um bloco, informe seu objetivo e limite. Implemente somente
  esse bloco e pare ao concluir; não avance para o próximo bloco na mesma rodada.
- Ao parar, apresente o que mudou, os arquivos envolvidos e as verificações
  feitas, e aguarde o usuário revisar e fazer o commit antes de continuar.
- O usuário é quem faz os commits. Não faça commits nem agrupe vários blocos num
  único conjunto de trabalho sem pedido explícito.
- Não trate a autorização para uma etapa inteira como autorização para executar
  todos os seus blocos. Continue apenas após o usuário confirmar o checkpoint e
  indicar que quer seguir.

## Objetivo

Construir e entregar a atividade **GenAI - CineData Analytics**, do Visagio Rocket Lab 2026.2: um agente que permite a pessoas não técnicas perguntar sobre o catálogo de filmes em linguagem natural e consultar, em tempo real, a camada Gold por Text-to-SQL.

A entrega deve ser um módulo backend FastAPI. O requisito central é a consulta analítica dos dados Gold; uma interface de chat não é obrigatória. O produto e a documentação devem refletir essa atividade GenAI, não a aplicação full-stack anterior.

## Fontes de verdade e resolução de dúvidas

Use esta ordem:

1. instrução explícita mais recente do usuário;
2. requisitos e orientações da atividade GenAI CineData Analytics;
3. esquema, dados e semântica efetivamente encontrados em `cinerocket.db`;
4. decisões registradas neste repositório e no TODO vigente.

Os requisitos da atividade definem o escopo obrigatório. Interface visual, memória, fallback, cache, avaliação formal, busca semântica e Databricks são possibilidades opcionais; não as converta em requisitos sem pedido do usuário. Não invente nomes de colunas, chaves, unidades, regras de negócio ou resultados. Confirme-os no banco antes de escrever consultas. Se o arquivo Gold não estiver disponível ou uma métrica for ambígua, avance no que for independente e registre a pendência claramente.

## Requisitos obrigatórios da atividade

- Implementar um agente para perguntas em linguagem natural sobre a camada Gold.
- Gerar e executar consultas de leitura em tempo real (Text-to-SQL).
- Usar Python.
- Usar um framework de agentes e um modelo à escolha do grupo. O modelo deve suportar tool calling para a abordagem de agente.
- Entregar um módulo backend FastAPI.
- Versionar o projeto no GitHub e manter um README com o passo a passo para obter/configurar dependências e executar a aplicação.
- Cobrir as categorias e perguntas-exemplo descritas no TODO interno.

Modelos gratuitos com sufixo `:free` pelo OpenRouter são uma opção, não uma
exigência. FastAPI é a arquitetura escolhida para este projeto; framework de
agente, provedor e modelo continuam configuráveis/escolhíveis. A cota informada
para o provedor gratuito pode ser de 50 chamadas por dia e uma pergunta pode
realizar mais de uma chamada. Os testes padrão devem usar mocks e não consumir
cota; chamadas reais devem ser poucas, manuais e contabilizadas.

## Fonte de dados Gold

O banco fornecido pela atividade chama-se `cinerocket.db`, é SQLite e contém as 10 tabelas abaixo. O projeto distribui o Gold via Git LFS para que esteja presente em clones; verifique que o objeto LFS foi baixado antes de executar Compose.

- `dim_movies`
- `fact_movies_performance`
- `dim_genres`
- `dim_people`
- `dim_companies`
- `dim_reviews`
- `movie_reviews`
- `bridge_movie_genre`
- `bridge_movie_person`
- `bridge_movie_company`

Use o arquivo Gold local como fonte direta das respostas do módulo GenAI. O
serviço abre `cinerocket.db` em modo somente leitura e não depende do banco
operacional ou das tabelas sociais da aplicação full-stack. O arquivo Gold é
distribuído via Git LFS e nunca deve ser alterado pelo agente. Não substitua a base
por dados inventados, TMDB ou chamadas online.

## Escopo e prioridades

Implemente primeiro o caminho mínimo completo: pergunta -> geração de consulta -> validação -> execução no banco Gold -> resposta em linguagem natural. A consulta precisa refletir o pedido, e a resposta deve ser sustentada pelo resultado executado.

As proteções necessárias para uma integração segura e funcional não são “extras”: restrinja o acesso ao Gold, rejeite operações de escrita e falhas de validação, trate erros de consulta/modelo e evite afirmar resultados que o SQL não retornou. O checklist detalhado de implementação e os critérios por etapa estão em [`TODO.md`](TODO.md).

São sugestões opcionais no enunciado: guardrails adicionais, interface visual, gráficos, memória de conversa, fallback entre modelos gratuitos, cache de respostas, avaliação com perguntas e respostas esperadas, combinação híbrida de SQL com busca semântica de sinopses e conexão ao Databricks. Só implemente uma dessas extensões após o fluxo obrigatório estar funcional e se ela couber no prazo ou for solicitada.

## Transição do produto anterior

Este repositório contém a aplicação full-stack CineData e um protótipo de
chatbot Gemini. O foco passa a ser um módulo GenAI Python/FastAPI independente,
que consulta diretamente o Gold. Preserve a aplicação e seu design durante a
construção do módulo. Depois que o novo backend estiver funcional, reaproveite
o frontend como camada visual e substitua o chatbot Gemini; mantenha as demais
funcionalidades existentes.

## Qualidade e segurança

- Não versionar chaves de provedores, arquivos `.env`, bancos locais recebidos da atividade ou artefatos temporários.
- A chave do provedor deve ser lida de configuração local/ambiente e nunca ir para o frontend, logs, prompt de saída ou resposta ao usuário.
- Não executar SQL livre gerado pelo modelo sem validação e controles de leitura.
- Manter consultas determinísticas quando possível e explicar limites relevantes (por exemplo, filtros de dados ausentes e período usado).
- Escrever respostas em português claro, coerentes com a pergunta e limitadas ao que os resultados sustentam.
- Não consumir chamadas de modelo sem necessidade; use validação local, fixtures e consultas de referência no desenvolvimento.
- Marcar itens do TODO como concluídos somente depois de cumprir o critério de saída correspondente. Identifique o que não foi executado ou não pôde ser confirmado.
- Revisar diff e documentação para remover afirmações herdadas da atividade anterior que conflitem com os requisitos atuais.

## Fora do escopo obrigatório

O enunciado não exige React, CRUD, autenticação, Docker, TMDB ou recursos
sociais. Desenvolva primeiro o backend GenAI em bloco independente; integre a
interface existente depois, reaproveitando seu design. Não acople o agente ao
backend social nem remova outras funcionalidades. O chatbot Gemini pode ser
retirado ao ser substituído pelo novo fluxo.

## Critério geral de conclusão

A entrega está pronta quando o agente em Python consulta o `cinerocket.db` real em tempo real, cobre os exemplos obrigatórios do enunciado com resultados corretos e explicáveis, documenta configuração e execução a partir de um clone, e o README descreve somente comandos e comportamentos verificados.
Não crie commits, altere histórico Git, publique ou modifique remotos sem pedido explícito do usuário.
