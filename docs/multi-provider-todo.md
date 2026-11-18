# Checklist: fallback entre provedores

## Organização

- [x] Conferir o estado do Git e a base da main.
- [x] Criar prod no commit 49cc10d da main (referência inicial, sem deploy).
- [x] Criar feat/multi-provider-fallback a partir da main.
- [x] Registrar o desenho técnico e os critérios de aceitação.
- [ ] Aprovar o desenho antes da implementação.

## Implementação

- [ ] Executar e registrar a suíte atual do GenAI como baseline.
- [ ] Criar plano de implementação com tarefas e verificações.
- [ ] Implementar adaptador OpenAI-compatible para Groq e OpenRouter.
- [ ] Normalizar mensagens, argumentos e resultados de ferramentas entre provedores.
- [ ] Criar roteador Gemini → Groq → OpenRouter, com ordem configurável.
- [ ] Ignorar provedores sem chave e validar nomes de provedores e limites.
- [ ] Implementar timeout de transporte, orçamento total por pergunta e cooldown.
- [ ] Evitar que retries internos multipliquem tentativas e tempo de espera.
- [ ] Atualizar capabilities e mensagens que hoje exigem especificamente Gemini.
- [ ] Preservar validação SQL, modo somente leitura, histórico e contratos HTTP.
- [ ] Atualizar .env.example, documentação e instruções Docker.

## Validação

- [ ] Testar serialização de tool calling, incluindo troca no meio da conversa.
- [ ] Simular timeout, 429, 5xx, chave inválida e resposta sem conteúdo utilizável.
- [ ] Testar ordem, ausência de chaves, cooldown e recuperação do provedor.
- [ ] Testar prazo total por pergunta, inclusive geração de insights.
- [ ] Testar esgotamento de todos os provedores e preservação do cache existente.
- [ ] Testar execução apenas com Groq ou apenas com OpenRouter configurado.
- [ ] Executar pytest e Ruff do GenAI.
- [ ] Avaliar Q01–Q14 em cada modelo com credenciais e cota disponíveis.
- [ ] Construir imagem e validar serviços no Docker.
- [ ] Revisar o diff antes de integrar na main.
- [ ] Promover para prod somente após validação e decisão explícita de integração.

Desenho: [fallback entre provedores](superpowers/specs/2026-11-18-multi-provider-design.md).
