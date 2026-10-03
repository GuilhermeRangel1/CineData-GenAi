import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ChatbotResultChart, temGraficoDeResultado } from './ChatbotResultChart'
import type { MetadadosGenAi } from '../types/api'

const metadata: MetadadosGenAi = {
  source: 'gold',
  query_id: null,
  metric: null,
  unit: null,
  period: null,
  population: null,
  limitations: null,
  columns: ['sk_movie_id', 'titulo', 'receita_brl'],
  row_count: 2,
  truncated: false,
  tool_calls: 1,
  cached: false,
}

describe('ChatbotResultChart', () => {
  it('mostra um gráfico para rankings de receita sem depender do código da pergunta', () => {
    const rows = [
      { sk_movie_id: 'm1', titulo: 'Filme A', receita_brl: 1200 },
      { sk_movie_id: 'm2', titulo: 'Filme B', receita_brl: 900 },
    ]

    render(<ChatbotResultChart metadata={metadata} rows={rows} />)

    expect(temGraficoDeResultado(metadata, rows)).toBe(true)
    expect(screen.getByText('Receita por filme')).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /Receita por filme/ })).toBeInTheDocument()
  })

  it('mostra um gráfico para rankings de orçamento em USD', () => {
    const budgetMetadata = { ...metadata, columns: ['titulo', 'orcamento_usd'] }
    const rows = [
      { titulo: 'Filme A', orcamento_usd: 200_000_000 },
      { titulo: 'Filme B', orcamento_usd: 150_000_000 },
    ]

    render(<ChatbotResultChart metadata={budgetMetadata} rows={rows} />)

    expect(temGraficoDeResultado(budgetMetadata, rows)).toBe(true)
    expect(screen.getByRole('img', { name: /Orçamento por filme/ })).toBeInTheDocument()
  })

  it('cria gráfico para uma resposta numérica sem regra cadastrada', () => {
    const genericMetadata = { ...metadata, columns: ['categoria', 'indice_personalizado'] }
    const rows = [
      { categoria: 'Aventura', indice_personalizado: 82 },
      { categoria: 'Drama', indice_personalizado: 64 },
    ]

    render(<ChatbotResultChart metadata={genericMetadata} rows={rows} />)

    expect(temGraficoDeResultado(genericMetadata, rows)).toBe(true)
    expect(screen.getByRole('img', { name: /Indice personalizado por Categoria/i })).toBeInTheDocument()
  })
})
