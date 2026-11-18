# Fallback entre provedores do chatbot

Data: 2026-11-18. Estado: implementado; Groq validado na versão atual, OpenRouter parcialmente validado e Gemini isolado aguarda credencial válida.

## Objetivo

Reduzir interrupções do chatbot quando um provedor ficar indisponível ou sem
cota, mantendo a interface, o histórico e as proteções atuais do banco Gold.
Não há garantia de disponibilidade absoluta nem de equivalência entre modelos.

## Situação antes da implementação

O agente usava ToolDefinition, ToolCall e ModelTurn como contrato interno.
GeminiToolCallingModel implementava esse contrato e tentava outro modelo Gemini
em falhas transitórias. A criação do agente e capabilities dependiam
exclusivamente da chave Gemini. SQL era validado e executado localmente em modo
somente leitura; provedores geravam pedidos de ferramentas, sem acesso ao banco.

## Abordagem escolhida como proposta

Integração direta com Gemini e Groq, com OpenRouter como terceira alternativa.
Usar somente OpenRouter simplificaria as integrações, mas concentraria a
disponibilidade em um único intermediário. Uma cadeia direta mantém a rota
Gemini independente das demais e aproveita o contrato já existente.

Criar um roteador que implemente o mesmo contrato interno do modelo. Preservar
o adaptador Gemini e adicionar um adaptador OpenAI-compatible compartilhado
por Groq e OpenRouter. Nenhuma credencial será enviada ao frontend ou registrada
em logs. Não adicionar chamadas paralelas especulativas, modelos locais ou
troca de modelo pela interface nesta entrega.

## Configuração e custos

Ordem padrão: gemini,groq,openrouter, configurável por GENAI_PROVIDER_ORDER.
Chaves opcionais: GENAI_GEMINI_API_KEY, GENAI_GROQ_API_KEY e
GENAI_OPENROUTER_API_KEY. Sem chave, o provedor é ignorado; sem nenhuma chave,
o guia local continua funcionando e a análise fica indisponível.

Preservar variáveis atuais do Gemini. Adicionar GENAI_GROQ_MODEL e
GENAI_OPENROUTER_MODEL. Para os novos provedores, exigir modelo explícito no
.env para não escolher automaticamente um serviço com cobrança. Credenciais e
modelo configurados autorizam o uso dessa rota; preço e limites pertencem ao
provedor. Não ativar seleção automática irrestrita de modelos no OpenRouter.

Chave sem modelo nos novos provedores desabilita apenas aquela rota, com aviso
seguro no log. Essa rota não conta para capabilities. Validar ordem na
inicialização: nomes desconhecidos ou duplicados são erros de configuração
explícitos, em vez de provocar tentativas ambíguas.

## Política de falhas e tempo

Trocar de provedor em falha de rede, timeout, 408, 429, 5xx, credencial rejeitada
ou resposta de protocolo sem conteúdo utilizável. Registrar apenas provedor,
modelo, duração e categoria de falha, sem chave, pergunta ou resposta bruta.
Erros locais de programação e rejeições do validador SQL não devem ser
classificados como indisponibilidade do provedor.

Defaults propostos: 12 segundos por chamada de transporte, 40 segundos de
orçamento de inferência por pergunta e cooldown de 60 segundos para falhas
transitórias. Credenciais rejeitadas desabilitam a rota até reiniciar o serviço
com a configuração corrigida. Limitar retries dos SDKs e contabilizar também o
fallback interno Gemini no orçamento. O deadline deve acompanhar todos os
turnos e insights da mesma pergunta; consultas SQL mantêm seus próprios limites.
Não simular timeout apenas abandonando threads que continuam consumindo API.

O orçamento de 40 segundos mede o tempo acumulado de inferência, pausado durante
SQL. Cada chamada recebe o menor valor entre 12 segundos e o saldo restante.
Se os dados já estiverem prontos quando o orçamento acabar, retornar a resposta
factual sem a etapa opcional de insights.

Cooldown é local ao processo, protegido contra acesso concorrente. Ao expirar,
permitir uma tentativa de recuperação, evitando múltiplas sondagens simultâneas.
Estado de uma pergunta não pode alterar a rota de outra pergunta em andamento.

## Tool calling e consistência

Cada adaptador traduz o histórico interno para o formato do provedor.
O adaptador OpenAI-compatible gera IDs de chamadas consistentes com as
respostas de ferramentas. Assinaturas específicas do Gemini não são enviadas
a outros provedores. Quando uma rota falhar após um tool call, o próximo
provedor recebe o histórico normalizado e o resultado já produzido localmente.
O provedor que funcionar passa a ser preferido nos próximos turnos daquela
pergunta. Testar também retorno ao Gemini com histórico criado por outro modelo.
Preservar a seleção simples/complexa do Gemini e passar todos os pedidos de SQL
pelo mesmo guard e executor. Não aceitar conteúdo vazio ou ferramentas com
argumentos inválidos como sucesso.

## Falha total e interface

Manter os caches existentes, sem remover o isolamento por conversa ou relaxar
suas regras de validade. Se uma entrada válida já puder responder, reutilizá-la.
Sem cache utilizável e sem provedor disponível, retornar erro compreensível de
indisponibilidade temporária. Não fabricar resposta ou indicar sucesso.

Capabilities passa a refletir a existência de uma rota configurada, e não a
saúde instantânea dos provedores. Textos de configuração devem mencionar os
provedores suportados, sem alterar o contrato HTTP usado pela interface.

## Aceitação e promoção

Testes determinísticos devem cobrir ordem, chaves ausentes, autenticação,
limites de uso, rede, cooldown, concorrência, deadline, falha total e tradução
de ferramentas. A suíte existente deve continuar passando. Validar imagem e
endpoints no Docker. Q01–Q14 precisam de avaliação real por modelo; testes com
fakes não comprovam qualidade analítica. A avaliação real Q01–Q14 passou de primeira no Groq, sem SQL de referência.
No OpenRouter, Q01–Q08 passaram na versão atual antes de timeout e falhas de API;
a rodada anterior de 14/14 usou uma cópia antiga do agente. Gemini isolado
aguarda uma chave válida.

prod começou como referência local do commit 49cc10d; isso não equivale a uma
certificação de release. A implementação permanece em feat/multi-provider-fallback.
Integração na main e promoção para prod dependem de revisão e decisão explícita.


## Resultado da validação

Groq passou Q01–Q14 na primeira tentativa em uma avaliação isolada da versão atual, sem SQL de referência ou correção. OpenRouter passou Q01–Q08 nessa versão; a chamada de Q09 expirou e a API falhou nas seguintes. Uma avaliação anterior de 14/14 do OpenRouter usou uma cópia antiga do agente. Os testes cobrem resultados tabulares no Gold atual. Gemini isolado aguarda uma chave válida (a anterior foi rejeitada com HTTP 400). Consulte `docs/genai/provider-validation.md` para detalhes e relatórios.
