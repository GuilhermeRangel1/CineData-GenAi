import { useId } from 'react'
import type { RobotMood } from './ChatbotRobot'

/** A complete temporary-mode character, drawn as one noir robot silhouette. */
export function ChatbotRobotNoir({ mood, compact }: { mood: RobotMood; compact: boolean }) {
  const id = useId().replace(/:/g, '')

  return (
    <svg className={`chatbot-robot ${compact ? 'chatbot-robot--compact' : ''}`} data-mood={mood} data-variant="temporary" viewBox="0 0 320 360" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}-coat`} x1="100" y1="187" x2="221" y2="298" gradientUnits="userSpaceOnUse">
          <stop stopColor="#4b5558" /><stop offset=".34" stopColor="#273137" /><stop offset=".75" stopColor="#151d22" /><stop offset="1" stopColor="#0b1116" />
        </linearGradient>
        <linearGradient id={`${id}-head`} x1="91" y1="54" x2="226" y2="184" gradientUnits="userSpaceOnUse">
          <stop stopColor="#687479" /><stop offset=".2" stopColor="#3e4a50" /><stop offset=".64" stopColor="#1b252b" /><stop offset="1" stopColor="#0d171e" />
        </linearGradient>
        <linearGradient id={`${id}-visor`} x1="115" y1="90" x2="202" y2="166" gradientUnits="userSpaceOnUse">
          <stop stopColor="#1b2c35" /><stop offset=".52" stopColor="#0b171e" /><stop offset="1" stopColor="#050c12" />
        </linearGradient>
        <linearGradient id={`${id}-hat`} x1="113" y1="21" x2="212" y2="82" gradientUnits="userSpaceOnUse">
          <stop stopColor="#59656a" /><stop offset=".28" stopColor="#303b40" /><stop offset=".72" stopColor="#111b21" /><stop offset="1" stopColor="#0a1319" />
        </linearGradient>
        <radialGradient id={`${id}-eye`} cx="42%" cy="34%" r="76%">
          <stop stopColor="#fff" /><stop offset=".4" stopColor="#f2fbfa" /><stop offset=".8" stopColor="#c3d9db" /><stop offset="1" stopColor="#728e95" />
        </radialGradient>
        <radialGradient id={`${id}-heart`}><stop stopColor="#fff" /><stop offset=".46" stopColor="#edf5f1" /><stop offset="1" stopColor="#9dbaae" /></radialGradient>
      </defs>

      <ellipse className="robot-shadow" cx="160" cy="329" rx="68" ry="9" fill="#a2b8b8" opacity=".17" />
      <g className="robot-float">
        <g className="robot-arm robot-arm--left">
          <path d="M106 193c-14-10-27-7-34 5-9 17-4 47 8 65 5 8 10 9 16 5 13-11 13-48 10-75Z" fill={`url(#${id}-coat)`} stroke="#819198" strokeOpacity=".52" strokeWidth="1.5" />
          <path d="M82 204c-4 19 0 39 7 52" fill="none" stroke="#acb8b9" strokeOpacity=".5" strokeWidth="3" strokeLinecap="round" />
          <path d="M92 265c6-9 10-26 10-39" fill="none" stroke="#0b1218" strokeWidth="3" strokeLinecap="round" />
        </g>
        <g className="robot-arm robot-arm--right">
          <path d="M214 193c14-10 27-7 34 5 9 17 4 47-8 65-5 8-10 9-16 5-13-11-13-48-10-75Z" fill={`url(#${id}-coat)`} stroke="#819198" strokeOpacity=".52" strokeWidth="1.5" />
          <path d="M239 203c4 18 0 39-7 52" fill="none" stroke="#a8b6b9" strokeOpacity=".45" strokeWidth="3" strokeLinecap="round" />
        </g>

        <g className="robot-body">
          <path d="M104 189c14-12 32-16 56-16s42 4 56 16l-8 70c-5 31-22 47-48 47s-43-16-48-47Z" fill={`url(#${id}-coat)`} stroke="#78888d" strokeOpacity=".7" strokeWidth="1.5" />
          <path d="M113 190c15 11 30 17 47 18 17-1 32-7 47-18l-9 61c-6 27-20 42-38 42s-32-15-38-42Z" fill="#1a252a" stroke="#829498" strokeOpacity=".45" />
          <path d="M112 191c12 11 25 17 40 19l-17 28-15-12Zm96 0c-12 11-25 17-40 19l17 28 15-12Z" fill="#39454a" stroke="#97a6a8" strokeOpacity=".53" strokeWidth="1.4" />
          <path d="M112 191c13 12 29 19 48 20 19-1 35-8 48-20" fill="none" stroke="#b8c5c4" strokeOpacity=".62" strokeWidth="2" strokeLinecap="round" />
          <path d="M160 209v74" fill="none" stroke="#a1afb0" strokeOpacity=".25" strokeWidth="1.5" />
          <circle cx="160" cy="242" r="18" fill="#0b141b" stroke="#718388" strokeWidth="2" />
          <circle className="robot-heart" cx="160" cy="242" r="11" fill={`url(#${id}-heart)`} />
          <g fill="#26383c" stroke="#26383c" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="160" cy="241" r="2.6" stroke="none" />
            <path d="M154.5 249c1.5-3.4 9.5-3.4 11 0v1h-11Z" stroke="none" />
            <path d="M156.4 237.8c.8-2.8 2.1-4.2 3.6-4.2s2.8 1.4 3.6 4.2Z" fill="none" strokeWidth="1.5" />
            <path d="M153 238.5c2.1-.9 4.4-1.3 7-1.3s4.9.4 7 1.3c-1.5 1.2-3.8 1.8-7 1.8s-5.5-.6-7-1.8Z" stroke="none" />
          </g>
          <path d="M121 216c1 36 10 63 27 78" fill="none" stroke="#a8b7b5" strokeOpacity=".23" strokeWidth="3" strokeLinecap="round" />
          <path d="M176 279h13" fill="none" stroke="#a5b3b4" strokeOpacity=".45" strokeWidth="2" strokeLinecap="round" />
        </g>

        <g className="robot-head">
          <path d="M79 118c0-51 32-82 81-82s81 31 81 82c0 45-28 69-81 69s-81-24-81-69Z" fill={`url(#${id}-head)`} stroke="#a5b4b7" strokeOpacity=".65" strokeWidth="1.8" />
          <path d="M91 112c2-29 23-46 69-46s67 17 69 46l-3 29c-4 25-25 39-66 39s-62-14-66-39Z" fill="#66777b" opacity=".5" />
          <path d="M96 111c4-25 27-39 64-39s60 14 64 39l-2 28c-3 24-24 37-62 37s-59-13-62-37Z" fill={`url(#${id}-visor)`} stroke="#9bacac" strokeOpacity=".8" strokeWidth="2" />
          <path d="M105 107c11-18 30-27 55-27s44 9 55 27" fill="none" stroke="#e2edeb" strokeOpacity=".22" strokeWidth="2" strokeLinecap="round" />
          <path d="M102 118c15-26 56-39 95-31-39-3-73 13-94 39Z" fill="#d7e6e5" opacity=".08" />
          <g className="robot-gaze">
            <g className="robot-eyes">
              <ellipse cx="132" cy="127" rx="17" ry="20" fill="#eefbfa" opacity=".12" />
              <ellipse cx="188" cy="127" rx="17" ry="20" fill="#eefbfa" opacity=".12" />
              <g className="robot-eye robot-eye--left">
                <ellipse cx="132" cy="127" rx="11.5" ry="15" fill={`url(#${id}-eye)`} />
                <ellipse cx="128" cy="121" rx="3" ry="4" fill="#fff" opacity=".85" />
              </g>
              <g className="robot-eye robot-eye--right">
                <ellipse cx="188" cy="127" rx="11.5" ry="15" fill={`url(#${id}-eye)`} />
                <ellipse cx="184" cy="121" rx="3" ry="4" fill="#fff" opacity=".85" />
              </g>
            </g>
            <g className="robot-smile" fill="none" stroke="#f4fbfa" strokeWidth="5" strokeLinecap="round">
              <path d="M120 133q12-20 24 0M176 133q12-20 24 0" />
            </g>
          </g>
          <circle cx="230" cy="128" r="3" fill="#dbe9e5" />
          <path d="M107 167c19 10 87 10 106 0" fill="none" stroke="#b8c9c8" strokeOpacity=".2" strokeWidth="2" strokeLinecap="round" />

          {/* The fedora grows from the head casing; its brim meets the upper visor. */}
          <path d="M99 78c2-19 12-41 24-50 5-4 12-4 19-2l18 5 18-5c7-2 14-2 19 2 12 9 22 31 24 50-17 8-39 12-61 12s-44-4-61-12Z" fill={`url(#${id}-hat)`} stroke="#899a9e" strokeWidth="1.7" />
          <path d="M119 34c-8 13-12 28-13 38m95-38c8 13 12 28 13 38" fill="none" stroke="#b7c4c4" strokeOpacity=".24" strokeWidth="2" strokeLinecap="round" />
          <path d="M107 67c17 7 35 10 53 10s36-3 53-10l3 9c-18 8-37 11-56 11s-38-3-56-11Z" fill="#738187" stroke="#aebcbc" strokeOpacity=".45" strokeWidth="1" />
          <path d="M68 81c31-8 61-9 92-7 31-2 61-1 92 7-16 11-48 17-92 17s-76-6-92-17Z" fill="#111b21" stroke="#9baeb1" strokeWidth="1.6" />
          <path d="M87 82c43 9 103 9 146 0" fill="none" stroke="#d3e0de" strokeOpacity=".38" strokeWidth="2" strokeLinecap="round" />
        </g>
      </g>
    </svg>
  )
}
