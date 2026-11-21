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
  it.each([
    ['variação da bilheteria anual', 'receita_brl', 'Bilheteria registrada por ano'],
    ['lucro total', 'lucro_brl', 'Lucro total por ano'],
    ['nota média simples no IMDb', 'nota_media_imdb', 'Nota média no IMDb por ano'],
  ])('mostra %s mesmo quando a contagem vem primeiro', (metric, column, title) => {
    const annual = { ...metadata, metric, columns: ['ano_lancamento', 'total_filmes', column] }
    const rows = [
      { ano_lancamento: 2022, total_filmes: 400, [column]: 6.2 },
      { ano_lancamento: 2023, total_filmes: 324, [column]: 6.3 },
    ]

    render(<ChatbotResultChart metadata={annual} rows={rows} />)

    expect(screen.getByRole('img', { name: new RegExp(title) })).toBeInTheDocument()
    expect(screen.queryByText('400')).not.toBeInTheDocument()
    expect(temGraficoDeResultado(annual, [rows[0], { ...rows[1], [column]: null }])).toBe(false)
  })

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

  it('organiza a série anual em ordem cronológica mesmo se a resposta chegar invertida', () => {
    const yearlyMetadata = {
      ...metadata,
      query_id: 'Q06',
      columns: ['ano_lancamento', 'filmes_validos', 'nota_imdb_media'],
    }
    const rows = [
      { ano_lancamento: 2026, filmes_validos: 12, nota_imdb_media: 7.3 },
      { ano_lancamento: 2024, filmes_validos: 18, nota_imdb_media: 7.1 },
      { ano_lancamento: 2025, filmes_validos: 15, nota_imdb_media: 7.2 },
    ]

    const { container } = render(<ChatbotResultChart metadata={yearlyMetadata} rows={rows} />)

    expect(
      [...container.querySelectorAll('.chatbot-chart-x-label')].map((label) => label.textContent),
    ).toEqual(['2024', '2025', '2026'])
  })
})
