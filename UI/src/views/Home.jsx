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
  return (
    <div className="mx-auto flex min-h-screen max-w-4xl flex-col px-8">
      <header className="pt-20 pb-14 text-center">
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

      <footer className="mt-auto flex items-center justify-center gap-3 pb-6 text-xs text-zinc-600">
        <span>UMUPY 3.0</span>
        <span>·</span>
        <button onClick={() => onNavigate('setup')} className="text-zinc-500 transition-colors hover:text-zinc-200">
          Setup
        </button>
      </footer>
    </div>
  )
}
