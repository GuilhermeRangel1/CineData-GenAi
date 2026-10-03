import { useId } from 'react'
import { ChatbotRobotNoir } from './ChatbotRobotNoir'

export type RobotMood = 'idle' | 'listening' | 'thinking' | 'happy' | 'error' | 'waving'

/** Vector companion: the shell, visor and eyes stay crisp at every display size. */
export function ChatbotRobot({ mood = 'idle', compact = false, incognito = false }: { mood?: RobotMood; compact?: boolean; incognito?: boolean }) {
  const id = useId().replace(/:/g, '')
  if (incognito) return <ChatbotRobotNoir mood={mood} compact={compact} />
  return (
    <svg className={`chatbot-robot ${compact ? 'chatbot-robot--compact' : ''}`} data-mood={mood} data-variant="default" viewBox="0 0 320 360" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-shell`} x1="67" y1="45" x2="242" y2="204" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff" /><stop offset=".28" stopColor="#f9fcfc" /><stop offset=".68" stopColor="#dce9ed" /><stop offset="1" stopColor="#94acb7" />
        </linearGradient>
        <radialGradient id={`${id}-head-shade`} cx="117" cy="74" r="149" gradientUnits="userSpaceOnUse">
          <stop offset=".45" stopColor="#fff" stopOpacity="0" /><stop offset=".85" stopColor="#6b8b9b" stopOpacity=".08" /><stop offset="1" stopColor="#315466" stopOpacity=".34" />
        </radialGradient>
        <linearGradient id={`${id}-body`} x1="110" y1="200" x2="224" y2="300" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff" /><stop offset=".35" stopColor="#f2f8f9" /><stop offset=".73" stopColor="#cfdee4" /><stop offset="1" stopColor="#8baab8" />
        </linearGradient>
        <linearGradient id={`${id}-arm-left`} x1="72" y1="194" x2="110" y2="260" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff" /><stop offset=".45" stopColor="#e8f3f4" /><stop offset="1" stopColor="#91acb8" />
        </linearGradient>
        <linearGradient id={`${id}-arm-right`} x1="209" y1="194" x2="249" y2="263" gradientUnits="userSpaceOnUse">
          <stop stopColor="#fff" /><stop offset=".5" stopColor="#e6f1f3" /><stop offset="1" stopColor="#7898aa" />
        </linearGradient>
        <linearGradient id={`${id}-visor-rim`} x1="160" y1="78" x2="160" y2="172" gradientUnits="userSpaceOnUse">
          <stop stopColor="#91abb6" /><stop offset=".47" stopColor="#496979" /><stop offset="1" stopColor="#d8edf0" />
        </linearGradient>
        <linearGradient id={`${id}-visor`} x1="119" y1="79" x2="203" y2="172" gradientUnits="userSpaceOnUse">
          <stop stopColor="#203d4c" /><stop offset=".48" stopColor="#0b2230" /><stop offset="1" stopColor="#07121d" />
        </linearGradient>
        <radialGradient id={`${id}-eye`} cx="36%" cy="24%" r="80%">
          <stop stopColor="#f7fffc" /><stop offset=".16" stopColor="#d5fff5" /><stop offset=".48" stopColor="#91f4df" /><stop offset=".78" stopColor="#4acfc0" /><stop offset="1" stopColor="#239b99" />
        </radialGradient>
        <radialGradient id={`${id}-light`}><stop stopColor="#effff9" /><stop offset=".43" stopColor="#9ff5e6" /><stop offset="1" stopColor="#3aaca9" /></radialGradient>
        <linearGradient id={`${id}-glass`} x1="120" y1="86" x2="178" y2="145" gradientUnits="userSpaceOnUse">
          <stop stopColor="#c7faff" stopOpacity=".22" /><stop offset="1" stopColor="#c7faff" stopOpacity="0" />
        </linearGradient>
      </defs>
      <ellipse className="robot-shadow" cx="160" cy="329" rx="66" ry="9" fill="#6edbd1" opacity=".14" />
      <g className="robot-float">
        <g className="robot-arm robot-arm--left">
          <path d="M107 192c-24-19-38-7-38 14 0 28 10 60 24 62 12 2 15-39 14-76Z" fill={`url(#${id}-arm-left)`} stroke="#7799a7" strokeOpacity=".32" />
          <path d="M80 199c-4 19 1 42 8 52" fill="none" stroke="#fff" strokeOpacity=".74" strokeWidth="3" strokeLinecap="round" />
          <path d="M101 199c1 20-1 45-7 60" fill="none" stroke="#5c8492" strokeOpacity=".18" strokeWidth="2" strokeLinecap="round" />
        </g>
        <g className="robot-arm robot-arm--right">
          <path d="M213 192c24-19 38-7 38 14 0 28-10 60-24 62-12 2-15-39-14-76Z" fill={`url(#${id}-arm-right)`} stroke="#7799a7" strokeOpacity=".32" />
          <path d="M220 199c-1 20 1 45 7 60" fill="none" stroke="#fff" strokeOpacity=".62" strokeWidth="3" strokeLinecap="round" />
        </g>
        <g className="robot-body">
          <path d="M104 190c18-14 94-14 112 0l-7 62c-5 37-23 54-49 54s-44-17-49-54Z" fill={`url(#${id}-body)`} stroke="#adc5ce" strokeOpacity=".5" />
          <path d="M112 211c2 43 15 73 38 86" fill="none" stroke="#fff" strokeOpacity=".5" strokeWidth="3" strokeLinecap="round" />
          <path d="M207 216c-1 38-12 66-29 78" fill="none" stroke="#698b9b" strokeOpacity=".19" strokeWidth="3" strokeLinecap="round" />
          <ellipse cx="160" cy="190" rx="57" ry="13" fill="#7899a8" />
          <ellipse cx="160" cy="187" rx="49" ry="9" fill="#e1f1f3" />
          <ellipse cx="160" cy="185" rx="39" ry="4" fill="#fff" opacity=".65" />
          <path d="M124 214c-1 35 7 60 19 69" fill="none" stroke="#fff" strokeOpacity=".72" strokeWidth="4" strokeLinecap="round" />
          <circle cx="160" cy="236" r="16" fill="#8cabb6" opacity=".45" />
          <circle cx="160" cy="236" r="12" fill="#557785" />
          <circle cx="160" cy="236" r="9.5" fill="#c5e7e7" />
          <circle className="robot-heart" cx="160" cy="236" r="7" fill={`url(#${id}-light)`} />
          <circle cx="157.5" cy="233.5" r="2.5" fill="#fff" opacity=".75" />
          <path d="M151 276h18" stroke="#7197a5" strokeWidth="2" strokeLinecap="round" opacity=".55" />
        </g>
        <g className="robot-head">
          <path d="M78 121c0-55 32-85 82-85s82 30 82 85c0 43-29 65-82 65s-82-22-82-65Z" fill={`url(#${id}-shell)`} stroke="#fff" strokeOpacity=".72" strokeWidth="1.5" />
          <path d="M78 121c0-55 32-85 82-85s82 30 82 85c0 43-29 65-82 65s-82-22-82-65Z" fill={`url(#${id}-head-shade)`} />
          <path d="M95 85c10-23 30-34 58-35" fill="none" stroke="#fff" strokeWidth="5" strokeLinecap="round" opacity=".86" />
          <path d="M104 63c-13 14-19 34-19 58" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" opacity=".42" />
          <path d="M222 76c9 13 13 28 13 44" fill="none" stroke="#567b8a" strokeWidth="3" strokeLinecap="round" opacity=".2" />
          <path d="M97 108c5-21 29-31 63-31s58 10 63 31l-1 29c-3 23-25 34-62 34s-59-11-62-34Z" fill={`url(#${id}-visor-rim)`} />
          <path d="M101 109c5-18 28-27 59-27s54 9 59 27l-1 27c-3 21-24 31-58 31s-55-10-58-31Z" fill={`url(#${id}-visor)`} />
          <path d="M108 104c10-13 29-19 52-19s42 6 52 19" fill="none" stroke="#d5f5f7" strokeOpacity=".26" strokeWidth="2" strokeLinecap="round" />
          <path d="M107 106c13-20 64-29 99-8-26-6-66-5-99 26Z" fill={`url(#${id}-glass)`} />
          <path d="M116 93c16-7 44-10 64-6" fill="none" stroke="#fff" strokeOpacity=".12" strokeWidth="2" strokeLinecap="round" />
          <g className="robot-gaze">
            <g className="robot-eyes">
              <ellipse cx="131.5" cy="127" rx="14" ry="17" fill="#5be8d6" opacity=".12" />
              <ellipse cx="188.5" cy="127" rx="14" ry="17" fill="#5be8d6" opacity=".12" />
              <g className="robot-eye robot-eye--left">
                <ellipse cx="131.5" cy="127" rx="10.5" ry="14" fill={`url(#${id}-eye)`} />
                <ellipse cx="128" cy="121.5" rx="3" ry="4" fill="#fff" opacity=".78" />
                <ellipse cx="136.5" cy="134.5" rx="2" ry="2.5" fill="#d7fff5" opacity=".25" />
              </g>
              <g className="robot-eye robot-eye--right">
                <ellipse cx="188.5" cy="127" rx="10.5" ry="14" fill={`url(#${id}-eye)`} />
                <ellipse cx="185" cy="121.5" rx="3" ry="4" fill="#fff" opacity=".78" />
                <ellipse cx="193.5" cy="134.5" rx="2" ry="2.5" fill="#d7fff5" opacity=".25" />
              </g>
            </g>
            <g className="robot-smile" fill="none" stroke="#a7f8e9" strokeWidth="5" strokeLinecap="round">
              <path d="M121 133q10-21 21 0M178 133q10-21 21 0" />
            </g>
            <g className="robot-cheeks" fill="#83daca" opacity=".2"><ellipse cx="114" cy="147" rx="7" ry="3" /><ellipse cx="206" cy="147" rx="7" ry="3" /></g>
          </g>
          <circle cx="229" cy="126" r="3.2" fill="#79e6d9" />
          <circle cx="228" cy="125" r="1.1" fill="#e9fffa" />
          <path d="M116 172c23 10 65 11 89 0" fill="none" stroke="#567988" strokeOpacity=".17" strokeWidth="2" strokeLinecap="round" />
        </g>
      </g>
    </svg>
  )
}
