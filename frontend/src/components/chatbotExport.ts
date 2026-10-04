import type { MetadadosGenAi } from '../types/api'
import { contextoParaExibicao, formatarCelula, rotuloColuna } from './chatbotPresentation'

function escaparCsv(value: string) {
  return `"${value.replaceAll('"', '""')}"`
}

function nomeArquivo(value: string, extensao: string) {
  const base = value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')
  return `${base || 'analise-cinedata'}.${extensao}`
}

function baixarBlob(blob: Blob, nome: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = nome
  document.body.append(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 0)
}

function contextoDaAnalise(titulo: string, metadata: MetadadosGenAi) {
  return [
    ['Análise', titulo],
    ['Métrica', metadata.metric],
    ['Unidade', metadata.unit],
    ['Período', metadata.period],
    ['Recorte aplicado', metadata.population],
  ].filter(([, value]) => value)
}

export function baixarResultadoCsv({
  titulo,
  metadata,
  columns,
  rows,
}: {
  titulo: string
  metadata: MetadadosGenAi
  columns: string[]
  rows: Array<Record<string, unknown>>
}) {
  const linhas = [
    ...contextoDaAnalise(titulo, metadata).map(([label, value]) => [label, value]),
    [],
    columns.map((column) => rotuloColuna(column, metadata)),
    ...rows.map((row) => columns.map((column) => formatarCelula(column, row[column]))),
  ]
  const csv = `\uFEFF${linhas.map((linha) => linha.map((value) => escaparCsv(String(value ?? ''))).join(';')).join('\r\n')}\r\n`
  baixarBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), nomeArquivo(titulo, 'csv'))
}

function estilosDoGrafico() {
  return `
    text { font-family: Arial, sans-serif; }
    .chatbot-chart-axis { stroke: #b1dfd3; stroke-opacity: .32; stroke-width: 1; }
    .chatbot-chart-grid { stroke: #b1dfd3; stroke-opacity: .12; stroke-width: 1; }
    .chatbot-chart-bar { fill: #68cfc1; opacity: .88; }
    .chatbot-chart-bar.is-negative { fill: #ed7b85; }
    .chatbot-chart-label { fill: #c3d8d9; font-size: 11px; }
    .chatbot-chart-value { fill: #8fe2d5; font-size: 10px; font-weight: 650; }
    .chatbot-chart-line { fill: none; stroke: #79b9ff; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
    .chatbot-chart-area { opacity: .25; }
    .chatbot-chart-point { fill: #d8edff; stroke: #609ee9; stroke-width: 3; }
    .chatbot-chart-point-value { fill: #d9fff7; font-size: 10px; font-weight: 700; paint-order: stroke; stroke: #0f2027; stroke-width: 3px; stroke-linejoin: round; }
    .chatbot-chart-x-label, .chatbot-scatter-axis { fill: #9db7bc; font-size: 10px; }
    .chatbot-donut-track { fill: none; stroke: #d8eef0; stroke-opacity: .08; stroke-width: 22; }
    .chatbot-donut-segment { fill: none; stroke-width: 22; }
    .chatbot-donut-total { fill: #edf7f6; font-size: 15px; font-weight: 700; }
    .chatbot-donut-caption { fill: #91acb2; font-size: 10px; }
    .chatbot-donut-legend-label { fill: #c9d9da; font-size: 11px; }
    .chatbot-donut-legend-value { fill: #ecf5f4; font-size: 11px; font-weight: 700; }
    .chatbot-scatter-reference { stroke: #ed9ab1; stroke-opacity: .4; stroke-width: 1.5; stroke-dasharray: 5 5; }
    .chatbot-scatter-point { fill: #ed7d9e; stroke: #ffdfeb; stroke-width: 2; opacity: .86; }
  `
}

function carregarImagem(url: string) {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error('Não foi possível preparar o gráfico para download.'))
    image.src = url
  })
}

function linhasDoContexto(metadata: MetadadosGenAi) {
  return contextoParaExibicao(metadata)
    .map(([label, value]) => `${label}: ${value}`)
}

function quebrarLinha(contexto: CanvasRenderingContext2D, texto: string, larguraMaxima: number) {
  const linhas: string[] = []
  let linha = ''
  for (const palavra of texto.split(/\s+/)) {
    const tentativa = linha ? `${linha} ${palavra}` : palavra
    if (linha && contexto.measureText(tentativa).width > larguraMaxima) {
      linhas.push(linha)
      linha = palavra
    } else {
      linha = tentativa
    }
  }
  if (linha) linhas.push(linha)
  return linhas
}

export async function baixarGraficoPng({
  elemento,
  titulo,
  metadata,
}: {
  elemento: HTMLElement
  titulo: string
  metadata: MetadadosGenAi
}) {
  const svg = elemento.querySelector<SVGSVGElement>('svg.chatbot-chart')
  if (!svg) throw new Error('O gráfico não está disponível para exportação.')

  const copia = svg.cloneNode(true) as SVGElement
  copia.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
  copia.insertAdjacentHTML('afterbegin', `<style>${estilosDoGrafico()}</style>`)
  const viewBox = (svg.getAttribute('viewBox') ?? '0 0 720 240').split(/\s+/).map(Number)
  const larguraOriginal = viewBox[2] || 720
  const alturaOriginal = viewBox[3] || 240
  const largura = 1600
  const margem = 64
  const larguraConteudo = largura - margem * 2
  const contexto = linhasDoContexto(metadata)

  // Os valores no fim das barras podem avançar além do viewBox original.
  const limites = svg.getBBox()
  const origemX = Math.min(0, limites.x - 12)
  const origemY = Math.min(0, limites.y - 12)
  const larguraGrafico = Math.max(larguraOriginal, limites.x + limites.width + 12) - origemX
  const alturaGrafico = Math.max(alturaOriginal, limites.y + limites.height + 12) - origemY
  copia.setAttribute('viewBox', `${origemX} ${origemY} ${larguraGrafico} ${alturaGrafico}`)
  copia.setAttribute('width', String(larguraGrafico))
  copia.setAttribute('height', String(alturaGrafico))

  const escala = larguraConteudo / larguraGrafico
  const alturaImagem = Math.ceil(alturaGrafico * escala)
  const canvas = document.createElement('canvas')
  canvas.width = largura
  canvas.height = 1
  const contextoCanvas = canvas.getContext('2d')
  if (!contextoCanvas) throw new Error('O navegador não conseguiu gerar a imagem.')

  contextoCanvas.font = '21px Arial'
  const linhasContexto = contexto.flatMap((linha) => quebrarLinha(contextoCanvas, linha, larguraConteudo))
  const inicioContexto = 152
  const alturaLinha = 29
  const inicioGrafico = inicioContexto + linhasContexto.length * alturaLinha + 42
  canvas.height = Math.ceil(inicioGrafico + alturaImagem + 54)
  const desenho = canvas.getContext('2d')
  if (!desenho) throw new Error('O navegador não conseguiu gerar a imagem.')

  desenho.fillStyle = '#0f2027'
  desenho.fillRect(0, 0, largura, canvas.height)
  desenho.fillStyle = '#7ee1d0'
  desenho.font = '700 22px Arial'
  desenho.fillText('CINEDATA · ANÁLISE', margem, 48)
  desenho.fillStyle = '#eff7f5'
  desenho.font = '700 38px Arial'
  desenho.fillText(titulo, margem, 101)
  desenho.fillStyle = '#b7cbcd'
  desenho.font = '21px Arial'
  linhasContexto.forEach((linha, index) => desenho.fillText(linha, margem, inicioContexto + index * alturaLinha))

  const markup = new XMLSerializer().serializeToString(copia)
  const image = await carregarImagem(`data:image/svg+xml;charset=utf-8,${encodeURIComponent(markup)}`)
  desenho.drawImage(image, margem, inicioGrafico, larguraConteudo, alturaImagem)
  const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, 'image/png'))
  if (!blob) throw new Error('O navegador não conseguiu gerar a imagem.')
  baixarBlob(blob, nomeArquivo(titulo, 'png'))
}
