export interface YouTubePlayer {
  playVideo(): void
  pauseVideo(): void
  seekTo(seconds: number, allowSeekAhead?: boolean): void
  mute(): void
  unMute(): void
  destroy(): void
  getIframe(): HTMLIFrameElement
}

interface PlayerEvent {
  target: YouTubePlayer
}
interface PlayerOptions {
  host: string
  videoId: string
  playerVars: Record<string, string | number>
  events: {
    onReady: (event: PlayerEvent) => void
    onStateChange: (event: PlayerEvent & { data: number }) => void
    onError: () => void
    onAutoplayBlocked: () => void
  }
}
interface YouTubeApi {
  Player: new (element: HTMLElement, options: PlayerOptions) => YouTubePlayer
}

declare global {
  interface Window {
    YT?: YouTubeApi
    onYouTubeIframeAPIReady?: () => void
  }
}

let pending: Promise<YouTubeApi> | undefined
export function loadYouTube(): Promise<YouTubeApi> {
  if (window.YT?.Player) return Promise.resolve(window.YT)
  if (pending) return pending
  pending = new Promise<YouTubeApi>((resolve, reject) => {
    const script = document.createElement('script')
    const timer = window.setTimeout(() => {
      script.remove()
      reject(new Error('O player demorou a responder.'))
    }, 12000)
    script.src = 'https://www.youtube.com/iframe_api'
    script.async = true
    script.onerror = () => {
      clearTimeout(timer)
      script.remove()
      reject(new Error('Player indisponível.'))
    }
    window.onYouTubeIframeAPIReady = () => {
      clearTimeout(timer)
      if (window.YT) resolve(window.YT)
    }
    document.head.append(script)
  }).catch((error: unknown) => {
    pending = undefined
    throw error
  })
  return pending
}

export const HOME_TRAILER_ID = 'shW9i6k8cB0'
export const HOME_TRAILER_URL = `https://www.youtube.com/watch?v=${HOME_TRAILER_ID}`
export const HOME_STILL = 'https://image.tmdb.org/t/p/original/4HodYYKEIsGOdinkGi2Ucz6X9i0.jpg'

export function youtubeEmbedUrl(url: string): string | null {
  try {
    const parsed = new URL(url)
    let id = ''
    if (parsed.hostname === 'youtu.be') id = parsed.pathname.slice(1)
    else if (parsed.pathname.startsWith('/embed/')) id = parsed.pathname.split('/')[2] ?? ''
    else id = parsed.searchParams.get('v') ?? ''
    if (!/^[A-Za-z0-9_-]{11}$/.test(id)) return null
    return `https://www.youtube-nocookie.com/embed/${id}?rel=0`
  } catch {
    return null
  }
}
