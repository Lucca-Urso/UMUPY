const features = [
  {
    id: 'download',
    title: 'YouTube Downloader',
    description: 'Download videos and playlists as MP3 with embedded artwork, ready for RekordBox.',
    enabled: true,
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 3v12m0 0 4.5-4.5M12 15l-4.5-4.5" />
        <path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" />
      </svg>
    ),
  },
  {
    id: 'spotify',
    title: 'Spotify Converter',
    description: 'Turn any Spotify playlist into YouTube downloads with automatic track matching.',
    enabled: true,
    icon: (
      <svg viewBox="0 0 24 24" className="h-6 w-6 fill-none stroke-current" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M7.5 9.5c3-.8 6.5-.4 9 1.2M8 12.5c2.4-.6 5.2-.3 7.3 1M8.5 15.3c1.9-.4 4-.2 5.7.8" />
      </svg>
    ),
  },
  {
    id: 'rekordbox',
    title: 'RekordBox Playlists',
    description: 'Rebuild playlists from .txt or .xml exports directly inside the RekordBox database.',
    enabled: true,
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
    enabled: false,
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
        <p className="mt-1 text-sm text-zinc-500">Your music pipeline, from YouTube to the booth.</p>
      </header>

      <main className="grid grid-cols-1 gap-4 pb-16 sm:grid-cols-2">
        {features.map((feature) => (
          <button
            key={feature.id}
            onClick={() => feature.enabled && onNavigate(feature.id)}
            disabled={!feature.enabled}
            className={`group relative rounded-2xl border border-white/[0.08] bg-white/[0.04] p-6 text-left transition-all duration-200 ${
              feature.enabled
                ? 'cursor-pointer hover:border-white/[0.16] hover:bg-white/[0.07]'
                : 'cursor-not-allowed opacity-45'
            }`}
          >
            {!feature.enabled && (
              <span className="absolute top-4 right-4 rounded-full bg-white/[0.08] px-2.5 py-0.5 text-[11px] font-medium text-zinc-400">
                Soon
              </span>
            )}
            <div className="mb-4 flex h-11 w-11 items-center justify-center rounded-xl bg-white/[0.06] text-[#0a84ff]">
              {feature.icon}
            </div>
            <h2 className="text-[15px] font-semibold text-zinc-100">{feature.title}</h2>
            <p className="mt-1.5 text-[13px] leading-relaxed text-zinc-500">{feature.description}</p>
          </button>
        ))}
      </main>

      <footer className="mt-auto pb-6 text-center text-xs text-zinc-600">UMUPY 0.1</footer>
    </div>
  )
}
