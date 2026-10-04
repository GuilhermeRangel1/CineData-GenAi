import { describe, expect, it, vi } from 'vitest'
import { ErroDaApi, atualizarFilme, listarFilmes, obterFilme, perguntarGenAi } from './client'
import { movie } from '../test/movie'
import type { Pagina } from '../types/api'

const catalogo: Pagina<typeof movie> = {
  itens: [movie],
  meta: { pagina: 1, tamanho_pagina: 12, total_itens: 1, total_paginas: 1 },
}

describe('Cache do cliente da API', () => {
  it('reutiliza respostas recentes de catálogo e detalhes', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(catalogo)))
      .mockResolvedValueOnce(new Response(JSON.stringify(movie)))
    vi.stubGlobal('fetch', fetcher)

    const params = new URLSearchParams({ busca: 'cache-catalogo' })
    await listarFilmes(params)
    await listarFilmes(params)
    await obterFilme('cache-detalhe')
    await obterFilme('cache-detalhe')

    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(fetcher.mock.calls[0][1]).toMatchObject({ cache: 'no-store' })
  })

  it('limpa o cache depois de uma escrita para não exibir dados antigos', async () => {
    const fetcher = vi
      .fn()
      .mockResolvedValueOnce(new Response(JSON.stringify(catalogo)))
      .mockResolvedValueOnce(new Response(JSON.stringify(movie)))
      .mockResolvedValueOnce(new Response(JSON.stringify(catalogo)))
    vi.stubGlobal('fetch', fetcher)

    const params = new URLSearchParams({ busca: 'cache-invalidacao' })
    await listarFilmes(params)
    await atualizarFilme('cache-invalidacao', { titulo: 'Título atualizado' })
    await listarFilmes(params)

    expect(fetcher).toHaveBeenCalledTimes(3)
    expect(fetcher.mock.calls[1][1]).toMatchObject({ method: 'PATCH' })
  })
})

describe('Streaming do chatbot', () => {
  it('recompõe eventos divididos entre pacotes e devolve o resultado', async () => {
    const encoder = new TextEncoder()
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode('{"type":"progress","stage":"searching","message":"Buscando'))
        controller.enqueue(encoder.encode('…"}\n{"type":"result","data":{"answer":"Pronto","rows":[],"insights":[],"metadata":{"columns":[],"row_count":0,"truncated":false,"tool_calls":0}}}\n'))
        controller.close()
      },
    })
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(stream, {
      headers: { 'Content-Type': 'application/x-ndjson' },
    })))
    const progress = vi.fn()

    const response = await perguntarGenAi('Oi', [], 'conversa-1234', progress)

    expect(response.answer).toBe('Pronto')
    expect(progress).toHaveBeenCalledWith({ stage: 'searching', message: 'Buscando…' })
  })

  it('transforma um evento inválido em erro legível', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{invalid}\n', {
      headers: { 'Content-Type': 'application/x-ndjson' },
    })))

    await expect(perguntarGenAi('Oi')).rejects.toMatchObject({
      codigo: 'stream_error',
      message: 'O chatbot enviou uma resposta inválida. Tente novamente.',
    } satisfies Partial<ErroDaApi>)
  })
})
