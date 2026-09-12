import { useEffect, useState } from 'react'
import { call } from '../api'

const features = [
  {
    id: 'downloader',
    title: 'Downloader',
    description: 'Paste YouTube, Spotify or SoundCloud links and download the tracks as MP3, ready for RekordBox.',
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3v12m0 0 4.5-4.5M12 15l-4.5-4.5" />
        <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      </svg>
    ),
  },
  {
    id: 'synchronizer',
    title: 'Synchronizer',
    description: 'Keep a local folder or a RekordBox playlist in sync with your online playlists.',
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 9a8 8 0 0 1 14-3m2-3v6h-6" />
        <path d="M20 15a8 8 0 0 1-14 3m-2 3v-6h6" />
      </svg>
    ),
  },
  {
    id: 'builder',
    title: 'Playlist Builder',
    description: 'Create RekordBox playlists from a playlist file or a folder of music.',
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 6h16M4 12h16M4 18h9" />
        <circle cx="17.5" cy="17.5" r="2.5" />
        <path d="M20 17.5V13" />
      </svg>
    ),
  },
  {
    id: 'history',
    title: 'History',
    description: 'Browse past operations, downloaded tracks and failures with full logs.',
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v5l3.5 2" />
      </svg>
    ),
  },
]

export default function Home({ onNavigate }) {
  const [setup, setSetup] = useState(null)

  useEffect(() => {
    call('setup_status').then(setSetup)
  }, [])

  const toolsMissing = setup && (!setup.ffmpeg.ok || !setup.deno.ok)

  return (
    <div className="mx-auto flex min-h-screen max-w-4xl flex-col px-8">
      <div className="flex justify-end pt-6">
        <button
          onClick={() => onNavigate('setup')}
          className="flex items-center gap-2 rounded-full border border-white/[0.1] bg-white/[0.05] px-4 py-2 text-sm font-medium text-zinc-200 transition-colors hover:border-white/[0.2] hover:bg-white/[0.1]"
        >
          <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="3" />
            <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
          </svg>
          Setup
          {toolsMissing && <span className="h-2 w-2 rounded-full bg-[#ff9f0a]" />}
        </button>
      </div>

      <header className="pt-10 pb-14 text-center">
        <div className="mx-auto mb-6 flex h-16 w-16 items-center justify-center rounded-[20px] bg-gradient-to-br from-[#0a84ff] to-[#5e5ce6] shadow-lg shadow-[#0a84ff]/20">
          <svg viewBox="0 0 24 24" className="h-8 w-8 fill-none stroke-white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M9 18V6l10-2v11.5" />
            <circle cx="6.5" cy="18" r="2.5" />
            <circle cx="16.5" cy="15.5" r="2.5" />
          </svg>
        </div>
        <h1 className="text-5xl font-semibold tracking-tight text-white">UMUPY</h1>
        <p className="mt-3 text-lg text-zinc-400">Urso Music Uploader Python</p>
        <p className="mt-1 text-sm text-zinc-500">Your music pipeline, from the web to the booth.</p>
      </header>

      {toolsMissing && (
        <button
          onClick={() => onNavigate('setup')}
          className="mb-6 rounded-xl border border-[#ff9f0a]/30 bg-[#ff9f0a]/10 px-4 py-3 text-left text-sm text-[#ff9f0a] transition-colors hover:bg-[#ff9f0a]/15"
        >
          Some audio tools are missing, so downloads will fail. Open Setup to see what to install.
        </button>
      )}

      <main className="grid grid-cols-1 gap-4 pb-16 sm:grid-cols-2">
        {features.map((feature) => (
          <button
            key={feature.id}
            onClick={() => onNavigate(feature.id)}
            className="group relative cursor-pointer rounded-2xl border border-white/[0.08] bg-white/[0.04] p-6 text-left transition-all duration-200 hover:border-white/[0.16] hover:bg-white/[0.07]"
          >
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.06] text-[#0a84ff]">
              {feature.icon}
            </div>
            <h2 className="text-[15px] font-semibold text-zinc-100">{feature.title}</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">{feature.description}</p>
          </button>
        ))}
      </main>

      <footer className="mt-auto pb-6 text-center text-xs text-zinc-600">UMUPY 3.0</footer>
    </div>
  )
}
