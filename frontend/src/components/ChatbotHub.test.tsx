import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ChatbotHub } from './ChatbotHub'

describe('ChatbotHub GenAI', () => {
  it('envia a pergunta ao módulo GenAI e exibe os resultados sem IDs técnicos', async () => {
    const fetcher = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      status: 'success',
      answer: 'Resposta: Os filmes foram ordenados pela receita.',
      rows: [{ sk_movie_id: 1, titulo: 'Filme A', receita_brl: 1250 }],
      metadata: {
        source: 'gold',
        query_id: 'Q01',
        metric: 'receita por filme',
        unit: 'BRL',
        period: 'todo o Gold disponível',
        population: 'filmes com receita_brl não nula',
        limitations: 'sem orçamento',
        columns: ['sk_movie_id', 'titulo', 'receita_brl'],
        row_count: 1,
        truncated: false,
        tool_calls: 1,
      },
    }))))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()

    render(<ChatbotHub />)
    await user.type(screen.getByLabelText('Escreva sua mensagem'), 'Quais são os 10 filmes com maior receita em BRL?')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    expect(await screen.findByText('Filme A')).toBeInTheDocument()
    expect(screen.queryByText('Resposta: Os filmes foram ordenados pela receita.')).not.toBeInTheDocument()
    expect(screen.getByText('Filmes com maior receita')).toBeInTheDocument()
    expect(screen.getByText(/R\$.*1\.250,00/)).toBeInTheDocument()
    expect(screen.queryByText('sk_movie_id')).not.toBeInTheDocument()
    expect(screen.queryByText('Métrica')).not.toBeInTheDocument()
    expect(fetcher).toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/questions'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ question: 'Quais são os 10 filmes com maior receita em BRL?' }),
      }),
    )
  })

  it('exibe esclarecimento devolvido pela API sem quebrar a conversa', async () => {
    const fetcher = vi.fn(() => Promise.resolve(new Response(JSON.stringify({
      status: 'clarification',
      error: { code: 'ambiguous_question', message: 'Informe o período.', details: null },
    }), { status: 422 })))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()

    render(<ChatbotHub />)
    await user.type(screen.getByLabelText('Escreva sua mensagem'), 'Quais filmes tiveram melhor desempenho?')
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Informe o período.'))
    expect(screen.getByRole('status')).toHaveTextContent('Vamos tentar de novo?')
    expect(screen.getByLabelText('Escreva sua mensagem')).toBeEnabled()
  })

  it('mostra falha de conexão de forma clara e permite reenviar a pergunta', async () => {
    const fetcher = vi.fn()
      .mockRejectedValueOnce(new TypeError('NetworkError when attempting to fetch resource.'))
      .mockResolvedValueOnce(new Response(JSON.stringify({
        status: 'success', answer: 'A consulta retornou 1 resultado.',
        rows: [{ titulo: 'Filme A' }],
        metadata: { columns: ['titulo'], row_count: 1, truncated: false, tool_calls: 1 },
      })))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    const question = 'Quais filmes existem?'

    render(<ChatbotHub />)
    await user.type(screen.getByLabelText('Escreva sua mensagem'), question)
    await user.click(screen.getByRole('button', { name: 'Enviar mensagem' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/Não consegui conectar ao chatbot/)
    expect(screen.getByRole('button', { name: 'Tentar novamente' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Tentar novamente' }))

    expect(await screen.findByText('Filme A')).toBeInTheDocument()
    expect(fetcher).toHaveBeenCalledTimes(2)
    expect(screen.getAllByText(question)).toHaveLength(1)
  })

  it('acompanha digitação, consulta e resposta sem duplicar o envio pelo teclado', async () => {
    let responder!: (response: Response) => void
    const fetcher = vi.fn(() => new Promise<Response>((resolve) => { responder = resolve }))
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<ChatbotHub />)
    const input = screen.getByLabelText('Escreva sua mensagem')

    await user.type(input, 'Filmes')
    expect(screen.getByRole('status')).toHaveTextContent('Pode escrever.')
    await user.keyboard('{Shift>}{Enter}{/Shift}por gênero')
    expect(input).toHaveValue('Filmes\npor gênero')
    expect(fetcher).not.toHaveBeenCalled()
    await user.keyboard('{Enter}{Enter}')
    expect(fetcher).toHaveBeenCalledTimes(1)
    expect(input).toBeDisabled()
    expect(screen.getByRole('status')).toHaveTextContent('Vou consultar os dados')
    expect(screen.getByLabelText('Chatbot está respondendo')).toBeInTheDocument()

    await act(async () => responder(new Response(JSON.stringify({
      status: 'success', answer: 'Nenhum resultado.', rows: [],
      metadata: { columns: [], row_count: 0, truncated: false, tool_calls: 1 },
    }))))
    expect(screen.getByRole('status')).toHaveTextContent('Prontinho!')
    expect(screen.queryByLabelText('Chatbot está respondendo')).not.toBeInTheDocument()
    expect(screen.getByText(/Não encontrei resultados/)).toBeInTheDocument()
    expect(input).toBeEnabled()
    expect(input).toHaveFocus()
  })

  it('permite acenar para o robô sem consultar o provedor', async () => {
    const fetcher = vi.fn()
    vi.stubGlobal('fetch', fetcher)
    const user = userEvent.setup()
    render(<ChatbotHub />)
    await user.click(screen.getByRole('button', { name: 'Acenar para o robô' }))
    expect(screen.getByRole('status')).toHaveTextContent('Oii!')
    expect(screen.getByRole('main')).toHaveClass('chatbot-motion-on')
    expect(fetcher).not.toHaveBeenCalled()
  })
})
