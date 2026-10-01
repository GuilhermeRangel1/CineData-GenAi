import { useEffect, useRef, useState } from 'react'
import {
  HOME_STILL,
  HOME_TRAILER_ID,
  loadYouTube,
  type YouTubePlayer,
} from '../lib/youtube'
import { Icon } from './Icon'

const DELAY_DE_ABERTURA_MS = 450
const DELAY_DE_REVELACAO_MS = 4200
const PAUSA_ENTRE_REPRODUCOES_MS = 2200
const REVELACAO_APOS_REINICIO_MS = 650

export function Hero({ onExplore, paused = false }: { onExplore: () => void; paused?: boolean }) {
  const host = useRef<HTMLDivElement>(null)
  const section = useRef<HTMLElement>(null)
  const delay = useRef<number | null>(null)
  const revealDelay = useRef<number | null>(null)
  const replayDelay = useRef<number | null>(null)
  const player = useRef<YouTubePlayer | null>(null)
  const replaying = useRef(false)
  const mutedPreference = useRef(true)
  const [shouldLoad, setShouldLoad] = useState(false)
  const [ready, setReady] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [unavailable, setUnavailable] = useState(false)
  const [muted, setMuted] = useState(true)

  useEffect(() => {
    function clearDelay() {
      if (delay.current !== null) window.clearTimeout(delay.current)
      delay.current = null
    }
    function reset() {
      clearDelay()
      if (revealDelay.current !== null) window.clearTimeout(revealDelay.current)
      revealDelay.current = null
      if (replayDelay.current !== null) window.clearTimeout(replayDelay.current)
      replayDelay.current = null
      setShouldLoad(false)
      setReady(false)
      setPlaying(false)
    }
    function start() {
      if (paused) return
      clearDelay()
      setUnavailable(false)
      delay.current = window.setTimeout(() => {
        setShouldLoad(true)
        delay.current = null
      }, DELAY_DE_ABERTURA_MS)
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) start()
        else reset()
      },
      { threshold: 0.2 },
    )
    if (section.current) observer.observe(section.current)
    start()
    return () => {
      clearDelay()
      observer.disconnect()
    }
  }, [paused])

  useEffect(() => {
    if (!shouldLoad) return
    let active = true
    let instance: YouTubePlayer | undefined
    const hostElement = host.current
    const revealVideo = (waitMs = DELAY_DE_REVELACAO_MS) => {
      if (revealDelay.current !== null) window.clearTimeout(revealDelay.current)
      revealDelay.current = window.setTimeout(() => {
        if (active) setReady(true)
        revealDelay.current = null
      }, waitMs)
    }
    const timeout = window.setTimeout(() => {
      if (!active) return
      setUnavailable(true)
      setPlaying(false)
      setReady(false)
    }, 18000)

    void loadYouTube()
      .then((api) => {
        if (!active || !hostElement) return
        const mount = document.createElement('div')
        hostElement.replaceChildren(mount)
        instance = new api.Player(mount, {
          host: 'https://www.youtube-nocookie.com',
          videoId: HOME_TRAILER_ID,
          playerVars: {
            autoplay: 1,
            mute: 1,
            controls: 0,
            disablekb: 1,
            modestbranding: 1,
            playsinline: 1,
            start: 0,
            loop: 0,
            rel: 0,
            origin: window.location.origin,
          },
          events: {
            onReady: ({ target }) => {
              if (!active) return
              target.getIframe().title = 'Trailer oficial de Spider-Man: Across the Spider-Verse'
              target.getIframe().tabIndex = -1
              player.current = target
              if (mutedPreference.current) target.mute()
              else target.unMute()
              target.playVideo()
            },
            onStateChange: ({ data, target }) => {
              if (!active) return
              if (data === 1) {
                window.clearTimeout(timeout)
                setPlaying(true)
                setUnavailable(false)
                const revealWait = replaying.current
                  ? REVELACAO_APOS_REINICIO_MS
                  : DELAY_DE_REVELACAO_MS
                replaying.current = false
                revealVideo(revealWait)
              } else if (data === 2) {
                if (revealDelay.current !== null) window.clearTimeout(revealDelay.current)
                revealDelay.current = null
                setPlaying(false)
              } else if (data === 0) {
                if (revealDelay.current !== null) window.clearTimeout(revealDelay.current)
                revealDelay.current = null
                setPlaying(false)
                setReady(false)
                replaying.current = true
                if (replayDelay.current !== null) window.clearTimeout(replayDelay.current)
                replayDelay.current = window.setTimeout(() => {
                  replayDelay.current = null
                  if (!active) return
                  target.seekTo(0, true)
                  target.playVideo()
                }, PAUSA_ENTRE_REPRODUCOES_MS)
              }
            },
            onError: () => {
              if (!active) return
              window.clearTimeout(timeout)
              setUnavailable(true)
              setPlaying(false)
              setReady(false)
            },
            onAutoplayBlocked: () => {
              if (!active) return
              window.clearTimeout(timeout)
              setPlaying(false)
            },
          },
        })
      })
      .catch(() => {
        if (!active) return
        window.clearTimeout(timeout)
        setUnavailable(true)
        setPlaying(false)
        setReady(false)
      })

    return () => {
      active = false
      if (revealDelay.current !== null) window.clearTimeout(revealDelay.current)
      revealDelay.current = null
      if (replayDelay.current !== null) window.clearTimeout(replayDelay.current)
      replayDelay.current = null
      window.clearTimeout(timeout)
      instance?.destroy()
      player.current = null
      replaying.current = false
      hostElement?.replaceChildren()
    }
  }, [shouldLoad])

  function toggleSound() {
    mutedPreference.current = !mutedPreference.current
    setMuted(mutedPreference.current)
    if (mutedPreference.current) player.current?.mute()
    else player.current?.unMute()
  }

  const loadingTrailer = shouldLoad && !ready && !unavailable

  return (
    <>
      <section className="hero hero--editorial" id="inicio" aria-labelledby="hero-title" ref={section}>
        <img className="hero-still" src={HOME_STILL} alt="" fetchPriority="high" />
        <div
          className={`hero-video ${ready && playing && !unavailable ? 'is-ready' : ''}`}
          ref={host}
          aria-hidden="true"
        />
        <div className="hero-shade" />
        <div className="hero-content">
          <p className="eyebrow">
            <span className="red-line" /> ANIMAÇÃO · SONY PICTURES ANIMATION
          </p>
          <h1 id="hero-title" className="hero-title-long">
            Spider-Man:
            <br />
            <span>Across the</span>
            <br />
            Spider-Verse
          </h1>
          <div className="hero-meta">
            <span>2023</span>
            <span>2h 20min</span>
            <span>Dir. Joaquim Dos Santos</span>
          </div>
          <p className="hero-description">
            Miles Morales atravessa o multiverso e encontra outras versões do Homem-Aranha.
          </p>
          <div className="hero-genres">
            <span>Animação</span>
            <span>Ação</span>
            <span>Aventura</span>
          </div>
          <div className="hero-actions">
            <button className="button button-glass" onClick={onExplore}>
              Explorar animações <Icon name="arrow" />
            </button>
          </div>
          <p className="hero-credit">Seleção editorial · Trailer oficial da Sony Pictures</p>
        </div>
        <div className="hero-bottom">
          <a href="#colecoes" className="hero-scroll">
            DESCUBRA OUTRAS HISTÓRIAS <span>↓</span>
          </a>
          <div className="playback-controls">
            {ready && !unavailable && (
              <button
                className="icon-button"
                type="button"
                onClick={toggleSound}
                aria-label={muted ? 'Ativar som do trailer' : 'Silenciar trailer'}
                title={muted ? 'Ativar som' : 'Silenciar'}
              >
                <Icon name={muted ? 'mute' : 'volume'} />
              </button>
            )}
            {loadingTrailer && (
              <span className="playback-status is-loading" aria-live="polite">
                <span className="playback-status__indicator" aria-hidden="true" />
                CARREGANDO TRAILER
              </span>
            )}
          </div>
        </div>
      </section>
    </>
  )
}
