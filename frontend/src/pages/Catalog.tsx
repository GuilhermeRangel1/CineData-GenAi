import { useCallback, useEffect, useState } from 'react'
import { listarFilmes } from '../api/client'
import { Icon } from '../components/Icon'
import { MovieCard } from '../components/MovieCard'
import { useResource } from '../hooks/useResource'

const genres = [
  ['', 'Todos os filmes'],
  ['Animation', 'Animação'],
  ['Adventure', 'Aventura'],
  ['Science Fiction', 'Ficção científica'],
  ['Drama', 'Drama'],
  ['Comedy', 'Comédia'],
  ['Thriller', 'Suspense'],
] as const

export function Catalog({
  genre,
  onGenre,
  onOpen,
  revision = 0,
}: {
  genre: string
  onGenre: (value: string) => void
  onOpen: (id: string) => void
  revision?: number
}) {
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [order, setOrder] = useState('relevance')
  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [advanced, setAdvanced] = useState({
    pessoa: '',
    produtora: '',
    ano_inicial: '',
    ano_final: '',
    duracao_minima: '',
    duracao_maxima: '',
    nota_minima: '',
  })
  const [appliedAdvanced, setAppliedAdvanced] = useState(advanced)
  useEffect(() => {
    const timer = window.setTimeout(() => {
      const pessoa = advanced.pessoa.trim()
      const produtora = advanced.produtora.trim()
      const anoInicial = advanced.ano_inicial.trim()
      const anoFinal = advanced.ano_final.trim()
      const next = {
        ...advanced,
        pessoa: pessoa.length >= 3 ? pessoa : '',
        produtora: produtora.length >= 3 ? produtora : '',
        ano_inicial: /^\d{4}$/.test(anoInicial) ? anoInicial : '',
        ano_final: /^\d{4}$/.test(anoFinal) ? anoFinal : '',
      }
      const unchanged = Object.keys(next).every(
        (key) => appliedAdvanced[key as keyof typeof appliedAdvanced] === next[key as keyof typeof next],
      )
      if (!unchanged) {
        setAppliedAdvanced(next)
        setPage(1)
      }
    }, 450)
    return () => clearTimeout(timer)
  }, [advanced, appliedAdvanced])
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setQuery(search.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [search])
  const criarParametros = useCallback(
    (pagina: number) => {
      const params = new URLSearchParams({
        pagina: String(pagina),
        tamanho_pagina: '12',
        ordenar_por:
          order === 'recent' ? 'ano_lancamento' : order === 'title' ? 'titulo' : 'relevancia',
        direcao: order === 'title' ? 'asc' : 'desc',
      })
      params.set('priorizar_capa', 'true')
      if (query) params.set('busca', query)
      if (genre) params.set('genero', genre)
      for (const [key, value] of Object.entries(appliedAdvanced)) {
        const normalizado = key === 'nota_minima' ? value.trim().replace(',', '.') : value.trim()
        if (normalizado) params.set(key, normalizado)
      }
      return params
    },
    [query, genre, order, appliedAdvanced],
  )
  const loader = useCallback(
    (signal: AbortSignal) => listarFilmes(criarParametros(page), signal),
    [criarParametros, page],
  )
  const { data, loading, error, retry, isPreviousData } = useResource(loader, revision, true)
  useEffect(() => {
    if (!data || isPreviousData || loading || page >= data.meta.total_paginas) return
    void listarFilmes(criarParametros(page + 1)).catch(() => undefined)
  }, [criarParametros, data, isPreviousData, loading, page])
  if (data && page > Math.max(1, data.meta.total_paginas))
    setPage(Math.max(1, data.meta.total_paginas))
  const paginaExibida = isPreviousData ? (data?.meta.pagina ?? page) : page
  function changePage(value: number) {
    setPage(value)
    document.getElementById('catalogo')?.scrollIntoView({ block: 'start' })
  }
  return (
    <section className="catalog-section" id="catalogo" aria-labelledby="catalog-title">
      <div className="catalog-heading">
        <div>
          <p className="eyebrow">ENCONTRE SUA PRÓXIMA HISTÓRIA</p>
          <h2 id="catalog-title">O cinema não acaba aqui.</h2>
        </div>
        <label className="search">
          <Icon name="search" />
          <span className="sr-only">Buscar por título</span>
          <input
            type="search"
            placeholder="Qual filme você procura?"
            value={search}
            maxLength={100}
            onChange={(event) => setSearch(event.target.value)}
          />
        </label>
      </div>
      <div className="catalog-toolbar">
        <div className="genre-filters" aria-label="Filtrar por gênero">
          {genres.map(([value, label]) => (
            <button
              key={value}
              aria-pressed={genre === value}
              onClick={() => {
                setPage(1)
                onGenre(value)
              }}
            >
              {label}
            </button>
          ))}
        </div>
        <label className="sort-control">
          <span className="sr-only">Ordenar filmes</span>
          <select
            value={order}
            onChange={(event) => {
              setOrder(event.target.value)
              setPage(1)
            }}
          >
            <option value="relevance">Mais relevantes</option>
            <option value="recent">Mais recentes</option>
            <option value="title">Título: A–Z</option>
          </select>
        </label>
        <button
          className="advanced-filter-trigger"
          aria-expanded={advancedOpen}
          aria-controls="advanced-catalog-filters"
          onClick={() => setAdvancedOpen((value) => !value)}
        >
          <Icon name="filter" /> Filtros avançados
        </button>
      </div>
      {advancedOpen && (
        <div className="advanced-filters" id="advanced-catalog-filters">
          <label>
            Pessoa
            <input
              value={advanced.pessoa}
              onChange={(event) => setAdvanced((value) => ({ ...value, pessoa: event.target.value }))}
              placeholder="Direção ou elenco"
              maxLength={255}
            />
          </label>
          <label>
            Produtora
            <input
              value={advanced.produtora}
              onChange={(event) => setAdvanced((value) => ({ ...value, produtora: event.target.value }))}
              placeholder="Estúdio ou distribuidora"
              maxLength={255}
            />
          </label>
          <label>
            Ano, de
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={advanced.ano_inicial}
              onChange={(event) => setAdvanced((value) => ({ ...value, ano_inicial: event.target.value.replace(/[^\d]/g, '') }))}
            />
          </label>
          <label>
            Ano, até
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={advanced.ano_final}
              onChange={(event) => setAdvanced((value) => ({ ...value, ano_final: event.target.value.replace(/[^\d]/g, '') }))}
            />
          </label>
          <label>
            Duração mínima
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={advanced.duracao_minima}
              onChange={(event) => setAdvanced((value) => ({ ...value, duracao_minima: event.target.value.replace(/[^\d]/g, '') }))}
              placeholder="minutos"
            />
          </label>
          <label>
            Duração máxima
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={advanced.duracao_maxima}
              onChange={(event) => setAdvanced((value) => ({ ...value, duracao_maxima: event.target.value.replace(/[^\d]/g, '') }))}
              placeholder="minutos"
            />
          </label>
          <label>
            Nota mínima
            <input
              type="text"
              inputMode="decimal"
              pattern="[0-9]*[,.]?[0-9]*"
              value={advanced.nota_minima}
              onChange={(event) => setAdvanced((value) => ({ ...value, nota_minima: event.target.value.replace(/[^\d,.]/g, '') }))}
              placeholder="0 a 10"
            />
          </label>
          <div className="advanced-filter-actions">
            <button
              className="button button-ghost"
              onClick={() => {
                setAdvanced({ pessoa: '', produtora: '', ano_inicial: '', ano_final: '', duracao_minima: '', duracao_maxima: '', nota_minima: '' })
                setPage(1)
              }}
            >
              Limpar extras
            </button>
          </div>
        </div>
      )}
      <div aria-busy={loading}>
        <p className="result-count" role="status">
          {loading
            ? 'Buscando histórias…'
            : error
              ? 'Catálogo indisponível'
              : `${(data?.meta.total_itens ?? 0).toLocaleString('pt-BR')} ${data?.meta.total_itens === 1 ? 'filme' : 'filmes'}${query ? ` para “${query}”` : ' para descobrir'}`}
        </p>
        {error ? (
          <div className="empty-state" role="alert">
            <Icon name="film" />
            <h3>Uma pausa na sessão.</h3>
            <p>{error}</p>
            <button className="button button-light" onClick={retry}>
              Tentar novamente
            </button>
          </div>
        ) : loading && !data ? (
          <div className="movie-grid">
            {Array.from({ length: 6 }, (_, i) => (
              <div className="poster skeleton" key={i} />
            ))}
          </div>
        ) : !data?.itens.length ? (
          <div className="empty-state">
            <Icon name="search" />
            <h3>Nenhuma história por aqui. Ainda.</h3>
            <p>
              {query || genre || Object.values(advanced).some(Boolean)
                ? 'Experimente outro título ou remova os filtros.'
                : 'Os filmes cadastrados aparecerão neste catálogo.'}
            </p>
            {(query || genre || Object.values(advanced).some(Boolean)) && (
              <button
                className="button button-light"
                onClick={() => {
                  setSearch('')
                  setQuery('')
                  setPage(1)
                  onGenre('')
                  setAdvanced({ pessoa: '', produtora: '', ano_inicial: '', ano_final: '', duracao_minima: '', duracao_maxima: '', nota_minima: '' })
                }}
              >
                Limpar filtros
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="movie-grid">
              {data.itens.map((movie) => (
                <MovieCard key={movie.id} movie={movie} onOpen={onOpen} />
              ))}
            </div>
            <nav className="pagination" aria-label="Paginação do catálogo">
              <button
                className="button button-outline"
                disabled={loading || page === 1}
                onClick={() => changePage(page - 1)}
              >
                <Icon name="left" /> Anterior
              </button>
              <span>
                Página <strong>{paginaExibida}</strong> de {data.meta.total_paginas.toLocaleString('pt-BR')}
              </span>
              <button
                className="button button-outline"
                disabled={loading || page >= data.meta.total_paginas}
                onClick={() => changePage(page + 1)}
              >
                Próxima <Icon name="arrow" />
              </button>
            </nav>
          </>
        )}
      </div>
    </section>
  )
}
