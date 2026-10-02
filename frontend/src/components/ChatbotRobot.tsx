import { useId } from 'react'

export type RobotMood = 'idle' | 'listening' | 'thinking' | 'happy' | 'error' | 'waving'

/** Articulated SVG: expressions follow the real request state, animation stays in CSS. */
export function ChatbotRobot({ mood = 'idle', compact = false }: { mood?: RobotMood; compact?: boolean }) {
  const id = useId().replace(/:/g, '')
  return (
    <svg className={`chatbot-robot ${compact ? 'chatbot-robot--compact' : ''}`} data-mood={mood} viewBox="0 0 320 360" preserveAspectRatio="xMidYMid meet" shapeRendering="geometricPrecision" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-shell`} x1="0" y1="0" x2=".9" y2="1">
          <stop stopColor="#ffffff" /><stop offset=".28" stopColor="#f8fcfd" /><stop offset=".62" stopColor="#dce9ed" /><stop offset=".86" stopColor="#a9c1cb" /><stop offset="1" stopColor="#7896a8" />
        </linearGradient>
        <linearGradient id={`${id}-body`} x1="0" y1="0" x2="1" y2=".7">
          <stop stopColor="#91abbc" /><stop offset=".3" stopColor="#f5fafb" /><stop offset=".7" stopColor="#dce9ed" /><stop offset="1" stopColor="#7595a9" />
        </linearGradient>
        <linearGradient id={`${id}-visor`} x1="0" y1="0" x2=".8" y2="1">
          <stop stopColor="#213647" /><stop offset=".55" stopColor="#0b1825" /><stop offset="1" stopColor="#08101a" />
        </linearGradient>
        <radialGradient id={`${id}-light`}><stop stopColor="#cafff6" /><stop offset=".6" stopColor="#70ebdd" /><stop offset="1" stopColor="#2ea89f" /></radialGradient>
        <radialGradient id={`${id}-eye`} cx="36%" cy="25%" r="78%">
          <stop stopColor="#effffb" /><stop offset=".22" stopColor="#a9fff1" /><stop offset=".68" stopColor="#5bdcca" /><stop offset="1" stopColor="#29a99f" />
        </radialGradient>
      </defs>
      <ellipse className="robot-shadow" cx="160" cy="329" rx="66" ry="9" fill="#6edbd1" opacity=".14" />
      <g className="robot-float">
        <g className="robot-arm robot-arm--left">
          <path d="M107 192C84 173 70 184 70 205c0 29 9 60 23 63 12 2 15-39 14-76Z" fill={`url(#${id}-shell)`} stroke="#f3fcff" strokeOpacity=".35" />
          <path d="M79 201c-1 16 2 34 6 43" fill="none" stroke="#fff" strokeOpacity=".6" strokeWidth="3" strokeLinecap="round" />
        </g>
        <g className="robot-arm robot-arm--right">
          <path d="M213 192c23-19 37-8 37 13 0 29-9 60-23 63-12 2-15-39-14-76Z" fill={`url(#${id}-shell)`} stroke="#f3fcff" strokeOpacity=".35" />
        </g>
        <g className="robot-body">
          <path d="M104 190c18-14 94-14 112 0l-7 62c-5 37-23 54-49 54s-44-17-49-54Z" fill={`url(#${id}-body)`} />
          <ellipse cx="160" cy="191" rx="56" ry="12" fill="#7a9eaf" />
          <ellipse cx="160" cy="188" rx="48" ry="9" fill="#d8edf0" />
          <path d="M122 214c-1 36 8 62 21 69" fill="none" stroke="#fff" strokeOpacity=".6" strokeWidth="4" strokeLinecap="round" />
          <circle cx="160" cy="236" r="14" fill="#325665" opacity=".25" />
          <circle className="robot-heart" cx="160" cy="236" r="8" fill={`url(#${id}-light)`} />
          <path d="M151 275h18" stroke="#7197a5" strokeWidth="2" strokeLinecap="round" opacity=".5" />
        </g>
        <g className="robot-head">
          <path d="M79 121c0-55 31-84 81-84s81 29 81 84c0 43-28 64-81 64s-81-21-81-64Z" fill={`url(#${id}-shell)`} stroke="#fff" strokeOpacity=".6" />
          <path d="M96 85c10-23 30-34 57-35" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" opacity=".85" />
          <path d="M99 109c4-21 28-30 61-30s57 9 61 30l-1 27c-2 22-24 32-60 32s-58-10-60-32Z" fill={`url(#${id}-visor)`} stroke="#66838f" strokeWidth="2" />
          <path d="M105 109c7-16 29-22 55-22s48 6 55 22" fill="none" stroke="#a8d8e8" strokeOpacity=".18" strokeWidth="2" strokeLinecap="round" />
          <path d="M111 102c15-13 48-17 73-11" fill="none" stroke="#7994a7" strokeWidth="2" strokeLinecap="round" opacity=".22" />
          <g className="robot-gaze">
            <g className="robot-eyes">
              <ellipse cx="131.5" cy="127" rx="13" ry="16" fill="#36d8c9" opacity=".13" />
              <ellipse cx="188.5" cy="127" rx="13" ry="16" fill="#36d8c9" opacity=".13" />
              <ellipse className="robot-eye robot-eye--left" cx="131.5" cy="127" rx="10.5" ry="14" fill={`url(#${id}-eye)`} />
              <ellipse className="robot-eye robot-eye--right" cx="188.5" cy="127" rx="10.5" ry="14" fill={`url(#${id}-eye)`} />
              <ellipse cx="128.5" cy="121" rx="2.7" ry="3.8" fill="#fff" opacity=".66" />
              <ellipse cx="185.5" cy="121" rx="2.7" ry="3.8" fill="#fff" opacity=".66" />
            </g>
            <g className="robot-smile" fill="none" stroke="#92ffed" strokeWidth="6" strokeLinecap="round">
              <path d="M121 133q10-21 21 0M178 133q10-21 21 0" />
            </g>
            <g className="robot-cheeks" fill="#68cfe1" opacity=".25"><ellipse cx="115" cy="146" rx="7" ry="3" /><ellipse cx="205" cy="146" rx="7" ry="3" /></g>
          </g>
          <circle cx="228" cy="126" r="3" fill="#73dbd2" />
        </g>
      </g>
    </svg>
  )
}
