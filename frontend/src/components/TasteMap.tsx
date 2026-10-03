import { useEffect, useMemo, useState, type CSSProperties } from 'react'
import { obterMapaGostos, obterMapaGostosEmCache } from '../api/client'
import type { MapaGostos, NoMapaGostos } from '../types/api'
import { Icon } from './Icon'

const PALETA_DE_GENEROS = ['#ff528f', '#c48aff', '#35e3ef', '#ffd45b', '#6bed99', '#ff985c']

function corDoGenero(genero: string | null): string {
  if (!genero) return '#a47adf'
  return PALETA_DE_GENEROS[[...genero].reduce((total, letra) => total + letra.charCodeAt(0), 0) % PALETA_DE_GENEROS.length]
}

function normalizar(texto: string): string {
  return texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
}

type Posicao = { x: number; y: number }

function distribuir(nos: NoMapaGostos[]): Map<string, Posicao> {
  const avaliados = nos.filter((no) => no.tipo === 'avaliado')
  const recomendados = nos.filter((no) => no.tipo === 'recomendado')
  const centro = { x: 500, y: 275 }
  const resultado = new Map<string, Posicao>()
  const colocar = (itens: NoMapaGostos[], raioX: number, raioY: number, deslocamento: number) => {
    itens.forEach((no, indice) => {
      const angulo = deslocamento + (Math.PI * 2 * indice) / Math.max(1, itens.length)
      resultado.set(no.id, { x: centro.x + Math.cos(angulo) * raioX, y: centro.y + Math.sin(angulo) * raioY })
    })
  }
  colocar(avaliados, avaliados.length === 1 ? 0 : 185, avaliados.length === 1 ? 0 : 130, -Math.PI / 2)
  colocar(recomendados, 390, 205, -Math.PI / 2 + Math.PI / Math.max(1, recomendados.length))
  return resultado
}

export function TasteMap({ onOpenMovie, revision = 0 }: { onOpenMovie: (id: string) => void; revision?: number }) {
  const [busca, setBusca] = useState('')
  const [dados, setDados] = useState<MapaGostos | null>(
    () => obterMapaGostosEmCache({ limiteNos: 24, vizinhosPorFilme: 3 }),
  )
  const [erro, setErro] = useState('')
  const [selecionado, setSelecionado] = useState<NoMapaGostos | null>(null)
  const [tentativa, setTentativa] = useState(0)
  const [excluir, setExcluir] = useState<string[]>([])
  const [carregando, setCarregando] = useState(!dados)
  const [foco, setFoco] = useState<string | null>(null)

  useEffect(() => {
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      void obterMapaGostos({ limiteNos: 24, vizinhosPorFilme: 3, excluir }, controller.signal, tentativa > 0)
        .then((mapa) => {
          if (controller.signal.aborted) return
          setDados(mapa)
          setErro('')
          setSelecionado((atual) => mapa.nos.find((no) => no.id === atual?.id) ?? null)
        })
        .catch((error: unknown) => {
          if (!controller.signal.aborted) setErro(error instanceof Error ? error.message : 'Não foi possível montar o mapa.')
        })
        .finally(() => { if (!controller.signal.aborted) setCarregando(false) })
    }, 0)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [excluir, tentativa, revision])

  const posicoes = useMemo(() => distribuir(dados?.nos ?? []), [dados])
  const ativo = foco ?? selecionado?.id
  const nosPorId = useMemo(
    () => new Map((dados?.nos ?? []).map((no) => [no.id, no])),
    [dados],
  )
  const origemPorDestino = useMemo(
    () => new Map((dados?.arestas ?? []).map((aresta) => [aresta.destino, aresta.origem])),
    [dados],
  )
  const relacionados = useMemo(() => {
    const ids = new Set(ativo ? [ativo] : [])
    dados?.arestas.forEach((aresta) => {
      if (aresta.origem === ativo || aresta.destino === ativo) {
        ids.add(aresta.origem)
        ids.add(aresta.destino)
      }
    })
    return ids
  }, [ativo, dados])
  const encontrados = useMemo(() => {
    const termo = normalizar(busca.trim())
    return new Set(
      (dados?.nos ?? [])
        .filter((no) => normalizar(no.titulo).includes(termo))
        .map((no) => no.id),
    )
  }, [busca, dados])
  const corDaOrigem = (id: string) => corDoGenero(nosPorId.get(id)?.genero_principal ?? null)
  function atualizar() {
    setCarregando(true)
    setErro('')
    const anteriores = dados?.nos.filter((no) => no.tipo === 'recomendado').map((no) => no.id) ?? []
    // Se o catálogo se esgotou, mantém a exclusão até surgir uma nova alternativa.
    if (anteriores.length) setExcluir(anteriores)
    setTentativa((valor) => valor + 1)
    setBusca('')
    setSelecionado(null)
  }
  return (
    <main className="taste-map-page" id="mapa-de-gostos">
      <header className="taste-map-header">
        <div>
          <p className="eyebrow"><span className="red-line" />DESCOBERTA PESSOAL</p>
          <h1>Mapa de gostos</h1>
        </div>
      </header>

      <div className="taste-map-content">
        <section className="taste-map-controls" aria-label="Controles do mapa de gostos">
          <label className="taste-map-search"><Icon name="search" /><span className="sr-only">Pesquisar dentro do mapa</span><input value={busca} onChange={(event) => setBusca(event.target.value)} placeholder="Buscar um filme na malha" /></label>
          <button className="taste-map-refresh" type="button" disabled={carregando} onClick={atualizar}>↻ {carregando ? 'Buscando sugestões…' : 'Atualizar mapa'}</button>
        </section>

        {erro ? (
          <section className="taste-map-state" role="alert"><h2>O mapa não pôde ser aberto.</h2><p>{erro}</p><button className="button button-outline" type="button" onClick={() => setTentativa((valor) => valor + 1)}>Tentar novamente</button></section>
        ) : !dados ? (
          <section className="taste-map-loading" aria-label="Montando o mapa de gostos"><span className="skeleton" /><span className="skeleton" /><span className="skeleton" /></section>
        ) : dados.total_avaliados === 0 ? (
          <section className="taste-map-empty"><span><Icon name="film" /></span><h2>Seu mapa começa com um olhar.</h2><p>Quando você avaliar um filme, vamos conectar seus gêneros, pessoas e época a novas histórias do catálogo.</p></section>
        ) : busca.trim() && encontrados.size === 0 ? (
          <section className="taste-map-empty"><span><Icon name="search" /></span><h2>Nenhum ponto encontrado.</h2><p>Tente outro título para voltar a enxergar sua malha.</p></section>
        ) : (
          <section className="taste-map-workspace" aria-busy={carregando} aria-label="Grafo de filmes avaliados e recomendações">
            <div className="taste-map-graph-wrap">
              <svg className="taste-map-graph" viewBox="0 0 1000 550" role="group" aria-label="Grafo direcionado do seu mapa de gostos">
                <defs>
                  {PALETA_DE_GENEROS.concat('#a47adf').map((cor) => <marker key={cor} id={`arrow-${cor.slice(1)}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" style={{ fill: cor }} /></marker>)}
                  {dados.nos.filter((no) => no.url_poster).map((no) => <clipPath id={`clip-${no.id}`} key={`clip-${no.id}`}><circle cx="0" cy="0" r="14" /></clipPath>)}
                </defs>
                <circle className="taste-map-orbit taste-map-orbit--inner" cx="500" cy="275" r="170" />
                <ellipse className="taste-map-orbit" cx="500" cy="275" rx="390" ry="205" />
                {dados.arestas.map((aresta) => {
                  const origem = posicoes.get(aresta.origem)
                  const destino = posicoes.get(aresta.destino)
                  if (!origem || !destino) return null
                  const distancia = Math.hypot(destino.x - origem.x, destino.y - origem.y) || 1
                  const dx = (destino.x - origem.x) / distancia
                  const dy = (destino.y - origem.y) / distancia
                  const cor = corDaOrigem(aresta.origem)
                  const destaca = aresta.origem === ativo || aresta.destino === ativo
                  return <line key={`${aresta.origem}-${aresta.destino}`} className={`taste-map-edge ${destaca ? 'is-active' : ''}`} style={{ stroke: cor, strokeWidth: 1 + aresta.peso * 2, opacity: ativo && !destaca ? 0.09 : 0.75 }} x1={origem.x + dx * 23} y1={origem.y + dy * 23} x2={destino.x - dx * 21} y2={destino.y - dy * 21} markerEnd={`url(#arrow-${cor.slice(1)})`}><title>{`${nosPorId.get(aresta.origem)?.titulo} → ${nosPorId.get(aresta.destino)?.titulo}: ${aresta.explicacao}`}</title></line>
                })}
                {dados.nos.map((no) => {
                  const posicao = posicoes.get(no.id)
                  if (!posicao) return null
                  const origem = origemPorDestino.get(no.id)
                  const cor = origem ? corDaOrigem(origem) : corDoGenero(no.genero_principal)
                  const apagado = (ativo && !relacionados.has(no.id)) || (busca.trim() && !encontrados.has(no.id))
                  return <g className={`taste-map-node taste-map-node--${no.tipo} ${selecionado?.id === no.id ? 'is-selected' : ''}`} style={{ '--node-color': cor, opacity: apagado ? 0.22 : 1 } as CSSProperties} key={no.id} transform={`translate(${posicao.x} ${posicao.y})`} tabIndex={0} role="button" aria-label={`Abrir ${no.titulo}`} aria-pressed={selecionado?.id === no.id} onMouseEnter={() => setFoco(no.id)} onMouseLeave={() => setFoco(null)} onFocus={() => setFoco(no.id)} onBlur={() => setFoco(null)} onClick={() => setSelecionado(selecionado?.id === no.id ? null : no)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); setSelecionado(no) } }}>
                    <circle className="taste-map-node-halo" r="25" />
                    <circle className="taste-map-node-ring" r={no.tipo === 'avaliado' ? 22 : 19} style={{ stroke: cor }} />
                    {no.url_poster ? <image href={no.url_poster} x="-14" y="-21" width="28" height="42" preserveAspectRatio="xMidYMid slice" clipPath={`url(#clip-${no.id})`} /> : <circle className="taste-map-node-fallback" r="13" style={{ fill: no.tipo === 'avaliado' ? cor : undefined }} />}
                    {no.tipo === 'avaliado' && <text className="taste-map-score" y="36">{no.nota_usuario?.toFixed(1)}</text>}
                    <text className="taste-map-label" y={no.tipo === 'avaliado' ? 51 : 35}>{encurtar(no.titulo)}</text>
                  </g>
                })}
              </svg>
            </div>
            <aside className="taste-map-inspector" aria-live="polite">
              {selecionado ? <>
                {selecionado.url_poster ? <img src={selecionado.url_poster} alt="" /> : <span className="taste-map-inspector-fallback"><Icon name="film" /></span>}
                <p className="eyebrow">{selecionado.tipo === 'avaliado' ? 'SEU OLHAR' : 'SUGESTÃO PRÓXIMA'}</p>
                <h2>{selecionado.titulo}</h2>
                <p>{selecionado.ano_lancamento ?? 'Ano não informado'} · {selecionado.generos.join(' · ') || 'Sem gênero informado'}</p>
                <strong>{selecionado.tipo === 'avaliado' ? `${selecionado.nota_usuario?.toFixed(1)} / 10` : `${Math.round((selecionado.afinidade ?? 0) * 100)}% de afinidade`}</strong>
                {selecionado.tipo === 'recomendado' && <small>{dados.arestas.find((aresta) => aresta.destino === selecionado.id)?.explicacao ?? 'Sugestão próxima ao que você avaliou.'}</small>}
                {selecionado.tipo === 'recomendado' && <small>Vem de: {dados.arestas.filter((aresta) => aresta.destino === selecionado.id).map((aresta) => dados.nos.find((no) => no.id === aresta.origem)?.titulo).join(' · ')}</small>}
                <button className="button button-outline" type="button" onClick={() => onOpenMovie(selecionado.id)}>Ver filme <Icon name="arrow" /></button>
              </> : <><span className="taste-map-inspector-hint">+</span><h2>Escolha um ponto</h2><p>Clique em um filme para ver o caminho que o trouxe até sua malha.</p></>}
            </aside>
          </section>
        )}
        {dados && dados.total_avaliados > 0 && !dados.nos.some((no) => no.tipo === 'recomendado') && <p role="status" className="taste-map-footnote">Não há outras sugestões compatíveis nesta rodada. Avalie mais filmes para explorar novos caminhos.</p>}
        {dados && dados.total_avaliados > 0 && <p className="taste-map-footnote"><b>{dados.total_avaliados}</b> {dados.total_avaliados === 1 ? 'filme avaliado alimenta' : 'filmes avaliados alimentam'} este mapa. Avalie algo novo para recalcular suas conexões.</p>}
      </div>
    </main>
  )
}

function encurtar(titulo: string): string {
  return titulo.length > 22 ? `${titulo.slice(0, 20)}…` : titulo
}
