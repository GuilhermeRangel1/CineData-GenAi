import { useEffect, useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { atualizarComunidade, criarComunidade, entrarNaComunidade, ErroDaApi, listarComunidades, listarMembrosComunidade, registrarVisualizacaoComunidade, removerComunidade } from '../api/client'
import type { ComunidadeLeitura, UsuarioLeitura } from '../types/api'
import { CommunityChat } from './CommunityChat'
import { Dialog } from './Dialog'
import { Icon } from './Icon'

const ACCEPTED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])

function readImage(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onerror = () => reject(new Error('Não foi possível ler a imagem.'))
    reader.onload = () => resolve(String(reader.result))
    reader.readAsDataURL(file)
  })
}

export function CommunityHub({ usuario, onLoginRequested, onOpenMovie, onBusyChange }: {
  usuario: UsuarioLeitura | null
  onLoginRequested: () => void
  onOpenMovie: (id: string) => void
  onBusyChange?: (busy: boolean) => void
}) {
  const [communities, setCommunities] = useState<ComunidadeLeitura[]>([])
  const [selected, setSelected] = useState<ComunidadeLeitura | null>(null)
  const [visibleCount, setVisibleCount] = useState(4)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [editor, setEditor] = useState<'create' | ComunidadeLeitura | null>(null)
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [image, setImage] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<ComunidadeLeitura | null>(null)
  const firstNewCard = useRef<HTMLElement | null>(null)
  const previousCount = useRef(4)

  useEffect(() => {
    const controller = new AbortController()
    void listarComunidades(controller.signal)
      .then(setCommunities)
      .catch((failure: Error) => { if (!controller.signal.aborted) setError(failure.message) })
      .finally(() => { if (!controller.signal.aborted) setLoading(false) })
    return () => controller.abort()
  }, [])

  useEffect(() => {
    if (visibleCount > previousCount.current) {
      firstNewCard.current?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth', block: 'start' })
      firstNewCard.current?.focus({ preventScroll: true })
      previousCount.current = visibleCount
    }
  }, [visibleCount])

  const ordered = [...communities].sort((a, b) => b.visualizacoes - a.visualizacoes || a.nome.localeCompare(b.nome, 'pt-BR'))

  async function openCommunity(community: ComunidadeLeitura) {
    await manage(async () => {
      if (usuario) {
        const members = await listarMembrosComunidade(community.id)
        if (!members.some((member) => member.id === usuario.id)) {
          try { await entrarNaComunidade(community.id) }
          catch (failure) { if (!(failure instanceof ErroDaApi && failure.status === 409)) throw failure }
          setCommunities((items) => items.map((item) => item.id === community.id ? { ...item, quantidade_membros: item.quantidade_membros + 1 } : item))
        }
      }
      setSelected(community)
      void registrarVisualizacaoComunidade(community.id).then((updated) => {
        setCommunities((items) => items.map((item) => item.id === updated.id ? updated : item))
      }).catch(() => undefined)
    })
  }

  function openEditor(community: ComunidadeLeitura | 'create') {
    setError('')
    setName(community === 'create' ? '' : community.nome)
    setDescription(community === 'create' ? '' : community.descricao)
    setImage(community === 'create' ? null : community.imagem_url)
    setEditor(community)
  }

  function chooseImage(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    if (!ACCEPTED_IMAGE_TYPES.has(file.type) || file.size > 1_000_000) {
      setError('Escolha uma imagem PNG, JPEG ou WebP de até 1 MB.')
      event.target.value = ''
      return
    }
    setError('')
    void readImage(file).then(setImage).catch((failure: Error) => setError(failure.message))
  }

  async function manage(task: () => Promise<void>) {
    setBusy(true)
    onBusyChange?.(true)
    setError('')
    try { await task() }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'Não foi possível concluir a ação.') }
    finally { setBusy(false); onBusyChange?.(false) }
  }

  async function save(event: FormEvent) {
    event.preventDefault()
    if (!editor || !name.trim() || !description.trim()) return
    await manage(async () => {
      const data = { nome: name.trim(), descricao: description.trim(), imagem_url: image }
      const saved = editor === 'create' ? await criarComunidade(data) : await atualizarComunidade(editor.id, data)
      setCommunities((items) => [...items.filter((item) => item.id !== saved.id), saved])
      setEditor(null)
    })
  }

  return (
    <div className="community-page">
      <header className="community-header">
        <div>
          <p className="eyebrow"><span className="red-line" />CINEMA É EXPERIÊNCIA COLETIVA</p>
          <h1>Comunidades</h1>
        </div>
        {usuario?.role === 'admin' && <button className="button button-light" onClick={() => openEditor('create')}>+ Nova comunidade</button>}
      </header>
      <div className="community-content">
        {error && !editor && !deleting && <p className="form-error" role="alert">{error}</p>}
        {loading ? <p role="status">Carregando comunidades…</p> : communities.length === 0 ? (
          <div className="community-empty"><h2>A primeira conversa começa aqui.</h2><p>{usuario?.role === 'admin' ? 'Crie uma comunidade para começar.' : 'As comunidades aparecerão aqui assim que forem criadas.'}</p></div>
        ) : (
          <section aria-labelledby="community-discovery-title">
            <div className="community-section-heading"><h2 id="community-discovery-title">Mais vistas</h2><span>Encontre sua próxima conversa.</span></div>
            <div className="community-grid">
              {ordered.slice(0, visibleCount).map((community, index) => (
                <article className="community-discovery-card" key={community.id} tabIndex={-1} ref={index === previousCount.current ? firstNewCard : undefined}>
                  <div className={`community-card-art ${community.imagem_url ? 'has-image' : ''}`} aria-hidden="true">{community.imagem_url ? <img src={community.imagem_url} alt="" /> : <Icon name="film" />}<small>{String(index + 1).padStart(2, '0')}</small></div>
                  <div className="community-card-copy">
                    <h3>{community.nome}</h3><p>{community.descricao}</p>
                    <div className="community-card-bottom">
                      <span>{community.quantidade_membros} {community.quantidade_membros === 1 ? 'membro' : 'membros'}</span>
                      <button className="button community-enter" disabled={busy} aria-label={`Entrar em ${community.nome}`} onClick={() => void openCommunity(community)}>Entrar <span aria-hidden="true">↗</span></button>
                    </div>
                  </div>
                  {usuario?.role === 'admin' && <div className="community-card-admin"><button className="text-button" onClick={() => openEditor(community)}>Editar</button><button className="text-button danger-text" onClick={() => { setError(''); setDeleting(community) }}>Excluir</button></div>}
                </article>
              ))}
            </div>
            {visibleCount < communities.length && <button className="button button-outline community-more" onClick={() => setVisibleCount((count) => count + 4)}>Ver mais <span aria-hidden="true">↓</span></button>}
          </section>
        )}
      </div>
      {selected && <CommunityChat key={selected.id} community={selected} usuario={usuario} onClose={() => setSelected(null)} onLoginRequested={onLoginRequested} onOpenMovie={onOpenMovie} onMembershipChange={(delta) => setCommunities((items) => items.map((item) => item.id === selected.id ? { ...item, quantidade_membros: Math.max(0, item.quantidade_membros + delta) } : item))} />}
      {editor && <Dialog title={editor === 'create' ? 'Nova comunidade' : 'Editar comunidade'} className="editor-dialog" busy={busy} onClose={() => setEditor(null)}>
        <form className="community-editor" onSubmit={save}>
          <h2>{editor === 'create' ? 'Nova comunidade' : 'Editar comunidade'}</h2>
          <label>Nome<input data-initial-focus value={name} onChange={(event) => setName(event.target.value)} maxLength={120} required /></label>
          <label>Descrição<textarea value={description} onChange={(event) => setDescription(event.target.value)} maxLength={1000} rows={3} required /></label>
          <div className="community-image-field">
            <span>Imagem da comunidade</span>
            <div className="community-image-editor">{image ? <img src={image} alt="Prévia da imagem da comunidade" /> : <span className="community-image-fallback"><Icon name="film" /></span>}<div><label className="button button-outline community-image-upload">{image ? 'Trocar imagem' : 'Enviar imagem'}<input type="file" accept="image/png,image/jpeg,image/webp" onChange={chooseImage} /></label><small>PNG, JPEG ou WebP, até 1 MB.</small>{image && <button type="button" className="text-button profile-remove" onClick={() => setImage(null)}>Remover imagem</button>}</div></div>
          </div>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions"><button type="button" className="button button-outline" onClick={() => setEditor(null)} disabled={busy}>Cancelar</button><button className="button button-light" disabled={busy}>Salvar comunidade</button></div>
        </form>
      </Dialog>}
      {deleting && <Dialog title="Excluir comunidade" className="editor-dialog" busy={busy} onClose={() => setDeleting(null)}>
        <div className="community-editor"><h2>Excluir {deleting.nome}?</h2><p>As mensagens, respostas e reações também serão removidas.</p>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions"><button className="button button-outline" data-initial-focus onClick={() => setDeleting(null)} disabled={busy}>Cancelar</button><button className="button button-danger" disabled={busy} onClick={() => void manage(async () => { await removerComunidade(deleting.id); setCommunities((items) => items.filter((item) => item.id !== deleting.id)); setDeleting(null) })}>Excluir comunidade</button></div>
        </div>
      </Dialog>}
    </div>
  )
}
