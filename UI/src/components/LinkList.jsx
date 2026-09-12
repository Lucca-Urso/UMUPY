import { Card } from './ui'

export const PROVIDER_LABELS = { youtube: 'YouTube', spotify: 'Spotify', soundcloud: 'SoundCloud' }

export function detectProvider(url) {
  const value = (url || '').trim().toLowerCase()
  if (!value) return null
  if (/(^|\/\/|\.)(youtube\.com|youtu\.be|music\.youtube\.com)\//.test(value) || value.startsWith('youtu')) return 'youtube'
  if (/(^|\/\/|\.)spotify\.com\//.test(value) || value.startsWith('spotify:')) return 'spotify'
  if (/(^|\/\/|\.)soundcloud\.com\//.test(value)) return 'soundcloud'
  return null
}

export function ProviderBadge({ provider, className = '' }) {
  if (!provider) return null
  const colors = {
    youtube: 'bg-[#ff453a]/15 text-[#ff6961]',
    spotify: 'bg-[#30d158]/15 text-[#30d158]',
    soundcloud: 'bg-[#ff9f0a]/15 text-[#ff9f0a]',
  }
  return (
    <span className={`shrink-0 rounded-full px-2.5 py-0.5 text-[11px] font-medium ${colors[provider] || 'bg-white/[0.08] text-zinc-400'} ${className}`}>
      {PROVIDER_LABELS[provider] || provider}
    </span>
  )
}

export default function LinkList({ links, onChange, placeholder = 'https://...', autoFocus = true }) {
  const update = (index, value) => {
    const next = [...links]
    next[index] = value
    onChange(next)
  }
  const remove = (index) => onChange(links.filter((_, i) => i !== index))
  const add = () => onChange([...links, ''])

  return (
    <Card className="p-6">
      <label className="mb-2 block text-[13px] font-medium text-zinc-400">Playlist or track links</label>
      <div className="flex flex-col gap-2">
        {links.map((link, index) => {
          const provider = detectProvider(link)
          const invalid = link.trim() && !provider
          return (
            <div key={index} className="flex items-center gap-2">
              <input
                autoFocus={autoFocus && index === 0}
                value={link}
                onChange={(e) => update(index, e.target.value)}
                placeholder={placeholder}
                className={`min-w-0 flex-1 rounded-xl border bg-black/40 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-[#0a84ff] ${
                  invalid ? 'border-[#ff453a]/50' : 'border-white/[0.1]'
                }`}
              />
              <ProviderBadge provider={provider} />
              {links.length > 1 && (
                <button
                  onClick={() => remove(index)}
                  className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-zinc-500 transition-colors hover:bg-white/[0.08] hover:text-zinc-200"
                  aria-label="Remove link"
                >
                  <svg viewBox="0 0 12 12" className="h-3 w-3 fill-none stroke-current" strokeWidth="2" strokeLinecap="round">
                    <path d="M3 3l6 6M9 3l-6 6" />
                  </svg>
                </button>
              )}
            </div>
          )
        })}
      </div>
      <button onClick={add} className="mt-3 text-[13px] text-[#0a84ff] hover:underline">
        + Add another link
      </button>
      {links.some((l) => l.trim() && !detectProvider(l)) && (
        <p className="mt-2 text-xs text-[#ff6961]">Only YouTube, Spotify and SoundCloud links are supported.</p>
      )}
    </Card>
  )
}
