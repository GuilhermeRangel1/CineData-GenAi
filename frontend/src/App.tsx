import { useEffect, useState } from 'react'
import { Hero } from './components/Hero'
import { Icon } from './components/Icon'
import { MovieDetail } from './components/MovieDetail'
import { MovieShelf } from './components/MovieShelf'
import { Catalog } from './pages/Catalog'
import { Dialog } from './components/Dialog'
import { MovieForm } from './components/MovieForm'
import { AuthForm } from './components/AuthForm'
import { OwnProfile } from './components/OwnProfile'
import { CommunityHub } from './components/CommunityHub'
import { ListHub } from './components/ListHub'
import { FriendshipHub } from './components/FriendshipHub'
import { AnalyticsDashboard } from './components/AnalyticsDashboard'
import { TasteMap } from './components/TasteMap'
import { ChatbotHub } from './components/ChatbotHub'
import { atualizarUsuarioSessao, carregarSessao, encerrarSessao, salvarSessao, type Sessao } from './auth/session'
import { entrarComoAdministradorDeTeste } from './api/client'
import './App.css'

function App() {
  const [page, setPage] = useState<'home' | 'lists' | 'friends' | 'communities' | 'analytics' | 'taste-map' | 'chatbot'>('home')
  const [selected, setSelected] = useState<string | null>(null)
  const [genre, setGenre] = useState('')
  const [catalogVersion, setCatalogVersion] = useState(0)
  const [revision, setRevision] = useState(0)
  const [creating, setCreating] = useState(false)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [session, setSession] = useState<Sessao | null>(() => carregarSessao())
  const [authMode, setAuthMode] = useState<'login' | 'cadastro' | null>(null)
  const [profileOpen, setProfileOpen] = useState(false)
  const refresh = () => setRevision((value) => value + 1)
  useEffect(() => {
    if (import.meta.env.VITE_DEMO_MODE !== 'true') return
    const sessaoAtual = carregarSessao()
    if (sessaoAtual && sessaoAtual.usuario.role !== 'admin') return
    let ativo = true
    void entrarComoAdministradorDeTeste()
      .then((response) => {
        if (ativo) setSession(salvarSessao(response))
      })
      .catch(() => undefined)
    return () => {
      ativo = false
    }
  }, [])
  function showHome() {
    setPage('home')
  }
  function showLists() {
    setPage('lists')
  }
  function explore(value: string) {
    setGenre(value)
    setCatalogVersion((version) => version + 1)
    document.getElementById('catalogo')?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
    })
  }
  return (
    <div className="app-shell">
      <a className="skip-link" href={page === 'home' ? '#catalogo' : page === 'lists' ? '#minhas-listas' : page === 'friends' ? '#amigos' : page === 'analytics' ? '#analytics' : page === 'taste-map' ? '#mapa-de-gostos' : page === 'chatbot' ? '#assistente' : '#comunidades'}>
        Pular para o conteúdo
      </a>
      <header className={`topbar ${page !== 'home' ? 'topbar--solid' : ''} ${page === 'chatbot' ? 'topbar--chatbot' : ''}`}>
        <a className="brand" href="#inicio" aria-label="CineData, início" onClick={showHome}>
          <span className="brand-symbol">
            <Icon name="film" />
          </span>
          <span className="brand-name">CINEDATA</span>
        </a>
        <nav className="main-nav" aria-label="Navegação principal">
          <a href="#inicio" onClick={showHome}>Início</a>
          <button type="button" aria-current={page === 'lists' ? 'page' : undefined} onClick={showLists}>Minhas listas</button>
          <button type="button" aria-current={page === 'friends' ? 'page' : undefined} onClick={() => setPage('friends')}>Amigos</button>
          <button type="button" aria-current={page === 'communities' ? 'page' : undefined} onClick={() => setPage('communities')}>Comunidades</button>
          <button type="button" aria-current={page === 'chatbot' ? 'page' : undefined} onClick={() => setPage('chatbot')}>Assistente</button>
          {session && <button type="button" aria-current={page === 'taste-map' ? 'page' : undefined} onClick={() => setPage('taste-map')}>Mapa de gostos</button>}
          {session?.usuario.role === 'admin' && <button type="button" aria-current={page === 'analytics' ? 'page' : undefined} onClick={() => setPage('analytics')}>Analytics</button>}
        </nav>
        <a href="#catalogo" className="header-search" onClick={showHome}>
          <Icon name="search" />
          <span>Encontrar um filme</span>
        </a>
        {session ? (
          <div className="account-actions">
            <button className="profile-trigger" onClick={() => setProfileOpen(true)} aria-label="Abrir seu perfil">
              {session.usuario.avatar_url ? <img src={session.usuario.avatar_url} alt="" /> : <span>{session.usuario.nome.slice(0, 1).toUpperCase()}</span>}
              <span>Olá, {session.usuario.nome}</span>
            </button>
            {session.usuario.role === 'admin' && (
              <button
                className="button button-outline add-movie"
                data-dialog-focus-return
                onClick={() => {
                  setNotice('')
                  setCreating(true)
                }}
              >
                + Adicionar filme
              </button>
            )}
            <button
              className="text-button"
              onClick={() => {
                encerrarSessao()
                setSession(null)
              }}
            >
              Sair
            </button>
          </div>
        ) : (
          <div className="account-actions">
            <button className="text-button" onClick={() => setAuthMode('login')}>
              Entrar
            </button>
            <button className="button button-outline" onClick={() => setAuthMode('cadastro')}>
              Criar conta
            </button>
          </div>
        )}
      </header>
      {page === 'home' ? (
        <main>
          <Hero onExplore={() => explore('Animation')} paused={creating || selected !== null} />
          <div className="content-wrap">
          <div className="collection-intro" id="colecoes">
            <p className="eyebrow">HISTÓRIAS PARA TODOS OS OLHARES</p>
            <span>Explore o catálogo, um universo de cada vez.</span>
          </div>
          <MovieShelf
            title="A imaginação ganha vida."
            subtitle="Animações para ir além do mundo lá fora."
            genre="Animation"
            revision={revision}
            onOpen={setSelected}
            onExplore={explore}
          />
          <MovieShelf
            title="Fora da sua zona de conforto."
            subtitle="Futuros distantes, encontros cósmicos e novas fronteiras."
            genre="Science Fiction"
            revision={revision}
            onOpen={setSelected}
            onExplore={explore}
          />
          <Catalog
            key={catalogVersion}
            revision={revision}
            genre={genre}
            onGenre={setGenre}
            onOpen={setSelected}
          />
          </div>
        </main>
      ) : page === 'lists' ? (
        <ListHub
          key={session?.usuario.id ?? 'guest'}
          usuario={session?.usuario ?? null}
          onLoginRequested={() => setAuthMode('login')}
          onOpenMovie={setSelected}
        />
      ) : page === 'friends' ? (
        <FriendshipHub
          key={session?.usuario.id ?? 'guest'}
          usuario={session?.usuario ?? null}
          onLoginRequested={() => setAuthMode('login')}
          onOpenMovie={setSelected}
        />
      ) : page === 'chatbot' ? (
        <ChatbotHub
          key={session?.usuario.id ?? 'guest'}
          usuario={session?.usuario ?? null}
          onLoginRequested={() => setAuthMode('login')}
        />
      ) : page === 'analytics' ? (
        <AnalyticsDashboard onOpenMovie={setSelected} />
      ) : page === 'taste-map' ? (
        <TasteMap onOpenMovie={setSelected} revision={revision} />
      ) : (
        <main id="comunidades">
          <CommunityHub
            usuario={session?.usuario ?? null}
            onBusyChange={setBusy}
            onLoginRequested={() => setAuthMode('login')}
            onOpenMovie={setSelected}
          />
        </main>
      )}
      <footer className="footer">
        <a className="footer-brand" href="#inicio" onClick={showHome}>
          CINEDATA
        </a>
        <p>Histórias que ficam. Olhares que se encontram.</p>
        {page === 'home' ? (
          <details>
            <summary>Créditos do destaque</summary>
            <p>
              Spider-Man: Across the Spider-Verse © 2023 Sony Pictures Animation.{' '}
              <a href="https://www.youtube.com/watch?v=shW9i6k8cB0" target="_blank" rel="noreferrer">
                Trailer: Sony Pictures
              </a>
              . Projeto acadêmico, sem afiliação aos estúdios.
            </p>
          </details>
        ) : (
          <span className="community-footer-note">Cinema é experiência coletiva.</span>
        )}
        <div className="tmdb-attribution">
          <a href="https://www.themoviedb.org/" target="_blank" rel="noreferrer">
            <img
              src="https://www.themoviedb.org/assets/2/v4/logos/stacked-green.svg"
              alt="The Movie Database (TMDB)"
              loading="lazy"
            />
          </a>
          <span>This product uses the TMDB API but is not endorsed or certified by TMDB.</span>
        </div>
      </footer>
      {notice && (
        <div className="app-notice" role="status">
          <span>{notice}</span>
          <button
            className="icon-button"
            aria-label="Dispensar mensagem"
            onClick={() => setNotice('')}
          >
            <Icon name="close" />
          </button>
        </div>
      )}
      {creating && (
        <Dialog
          title="Adicionar filme"
          className="editor-dialog"
          busy={busy}
          onClose={() => setCreating(false)}
        >
          <MovieForm
            onBusyChange={setBusy}
            onCancel={() => setCreating(false)}
            onSaved={(movie) => {
              setCreating(false)
              setNotice('Filme cadastrado com sucesso.')
              refresh()
              setSelected(movie.id)
            }}
          />
        </Dialog>
      )}
      {authMode && (
        <Dialog
          title={authMode === 'cadastro' ? 'Criar conta' : 'Entrar'}
          className="editor-dialog"
          busy={busy}
          onClose={() => setAuthMode(null)}
        >
          <AuthForm
            mode={authMode}
            onBusyChange={setBusy}
            onAuthenticated={(newSession) => {
              setSession(newSession)
              setAuthMode(null)
            }}
          />
        </Dialog>
      )}
      {profileOpen && session && (
        <OwnProfile
            user={session.usuario}
            busy={busy}
            onBusyChange={setBusy}
            onClose={() => setProfileOpen(false)}
            onOpenMovie={setSelected}
            onSaved={(user) => {
              const updated = atualizarUsuarioSessao(user)
              if (updated) setSession(updated)
            }}
          />
      )}
      {selected && (
        <MovieDetail
          key={`${selected}-${session?.usuario.id ?? 'guest'}`}
          id={selected}
          onClose={() => setSelected(null)}
          onChanged={refresh}
          onDeleted={() => {
            refresh()
            setNotice('Filme e avaliações excluídos.')
            document.querySelector<HTMLElement>('.add-movie')?.focus()
          }}
          usuario={session?.usuario ?? null}
          onLoginRequested={() => setAuthMode('login')}
          onOpenLists={() => {
            setSelected(null)
            setPage('lists')
          }}
        />
      )}
    </div>
  )
}

export default App
