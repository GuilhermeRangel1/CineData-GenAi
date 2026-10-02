import { act, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Hero } from './Hero'
import { loadYouTube } from '../lib/youtube'

vi.mock('../lib/youtube', async (original) => ({
  ...(await original<typeof import('../lib/youtube')>()),
  loadYouTube: vi.fn(),
}))

const load = vi.mocked(loadYouTube)

afterEach(() => {
  vi.useRealTimers()
  load.mockReset()
})

describe('Destaque cinematográfico', () => {
  it('mantém a imagem até o trailer realmente começar a tocar', async () => {
    vi.useFakeTimers()
    const pauseVideo = vi.fn()
    const playVideo = vi.fn()
    const mute = vi.fn()
    const unMute = vi.fn()
    const destroy = vi.fn()
    type Options = ConstructorParameters<Awaited<ReturnType<typeof loadYouTube>>['Player']>[1]
    let options!: Options
    const target = {
      pauseVideo,
      playVideo,
      seekTo: vi.fn(),
      mute,
      unMute,
      destroy,
      getIframe: () => document.createElement('iframe'),
    }
    class Player {
      constructor(_element: HTMLElement, passed: Options) {
        options = passed
        return target
      }
    }
    load.mockResolvedValue({ Player } as unknown as Awaited<ReturnType<typeof loadYouTube>>)

    render(<Hero onExplore={vi.fn()} />)
    expect(document.querySelector('.hero-still')).toBeInTheDocument()
    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')

    await act(async () => {
      await vi.advanceTimersByTimeAsync(450)
      await Promise.resolve()
    })
    expect(options).toBeDefined()
    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')

    act(() => {
      options.events.onReady({ target })
      options.events.onStateChange({ target, data: 1 })
    })

    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')
    await act(async () => { await vi.advanceTimersByTimeAsync(4200) })
    expect(document.querySelector('.hero-video')).toHaveClass('is-ready')
    expect(mute).toHaveBeenCalled()
    fireEvent.click(screen.getByRole('button', { name: 'Ativar som do trailer' }))
    expect(unMute).toHaveBeenCalled()
  })

  it('volta à imagem e desmonta o player ao sair da área', async () => {
    vi.useFakeTimers()
    let observer: { trigger: (visible: boolean) => void } | undefined
    class ControlledObserver {
      constructor(callback: IntersectionObserverCallback) {
        observer = {
          trigger: (visible: boolean) => callback(
            [{ isIntersecting: visible } as IntersectionObserverEntry],
            {} as IntersectionObserver,
          ),
        }
      }
      observe() {}
      disconnect() {}
    }
    vi.stubGlobal('IntersectionObserver', ControlledObserver)
    const destroy = vi.fn()
    type Options = ConstructorParameters<Awaited<ReturnType<typeof loadYouTube>>['Player']>[1]
    let options!: Options
    const target = {
      pauseVideo: vi.fn(),
      playVideo: vi.fn(),
      seekTo: vi.fn(),
      mute: vi.fn(),
      unMute: vi.fn(),
      destroy,
      getIframe: () => document.createElement('iframe'),
    }
    class Player {
      constructor(_element: HTMLElement, passed: Options) {
        options = passed
        return target
      }
    }
    load.mockResolvedValue({ Player } as unknown as Awaited<ReturnType<typeof loadYouTube>>)

    render(<Hero onExplore={vi.fn()} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(450)
      await Promise.resolve()
    })
    expect(options).toBeDefined()
    act(() => options.events.onStateChange({ target, data: 1 }))
    await act(async () => { await vi.advanceTimersByTimeAsync(4200) })
    expect(document.querySelector('.hero-video')).toHaveClass('is-ready')

    act(() => observer?.trigger(false))
    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')
    expect(destroy).toHaveBeenCalled()

    act(() => observer?.trigger(true))
    await act(async () => {
      await vi.advanceTimersByTimeAsync(450)
      await Promise.resolve()
    })
    expect(load).toHaveBeenCalledTimes(2)
  })

  it('mantém o cartaz durante a pausa e reinicia o trailer quando ele termina', async () => {
    vi.useFakeTimers()
    const playVideo = vi.fn()
    const seekTo = vi.fn()
    const destroy = vi.fn()
    type Options = ConstructorParameters<Awaited<ReturnType<typeof loadYouTube>>['Player']>[1]
    let options!: Options
    const target = {
      pauseVideo: vi.fn(),
      playVideo,
      seekTo,
      mute: vi.fn(),
      unMute: vi.fn(),
      destroy,
      getIframe: () => document.createElement('iframe'),
    }
    class Player {
      constructor(_element: HTMLElement, passed: Options) {
        options = passed
        return target
      }
    }
    load.mockResolvedValue({ Player } as unknown as Awaited<ReturnType<typeof loadYouTube>>)

    render(<Hero onExplore={vi.fn()} />)
    await act(async () => {
      await vi.advanceTimersByTimeAsync(450)
      await Promise.resolve()
    })
    act(() => {
      options.events.onReady({ target })
      options.events.onStateChange({ target, data: 1 })
    })
    await act(async () => { await vi.advanceTimersByTimeAsync(4200) })
    expect(document.querySelector('.hero-video')).toHaveClass('is-ready')

    act(() => options.events.onStateChange({ target, data: 0 }))
    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')
    expect(document.querySelector('.hero-still')).toBeInTheDocument()

    await act(async () => { await vi.advanceTimersByTimeAsync(2200) })
    expect(seekTo).toHaveBeenCalledWith(0, true)
    expect(playVideo).toHaveBeenCalledTimes(2)
    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')

    act(() => options.events.onStateChange({ target, data: 1 }))
    await act(async () => { await vi.advanceTimersByTimeAsync(649) })
    expect(document.querySelector('.hero-video')).not.toHaveClass('is-ready')
    await act(async () => { await vi.advanceTimersByTimeAsync(1) })
    expect(document.querySelector('.hero-video')).toHaveClass('is-ready')
  })
})
