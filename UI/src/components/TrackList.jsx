import { Card, Checkbox } from './ui'
import { ProviderBadge } from './LinkList'

export function trackLabel(track) {
  const origin = track.origin || track
  const artists = origin.artists?.length ? `${origin.artists.join(', ')} - ` : ''
  return `${artists}${origin.title}`
}

export default function TrackList({ tracks, checked, onToggle, keyOf = (t) => t.id, maxHeight = '400px' }) {
  return (
    <Card className="overflow-y-auto" style={{ maxHeight }}>
      {tracks.map((track, index) => {
        const key = keyOf(track)
        const selected = checked.has(key)
        return (
          <div
            key={key}
            onClick={() => onToggle(key)}
            className={`flex cursor-pointer items-center gap-4 px-5 py-3 transition-colors hover:bg-white/[0.04] ${
              index > 0 ? 'border-t border-white/[0.05]' : ''
            }`}
          >
            <Checkbox checked={selected} onChange={() => onToggle(key)} />
            <div className="min-w-0 flex-1">
              <p className={`truncate text-sm ${selected ? 'text-zinc-100' : 'text-zinc-500'}`}>{trackLabel(track)}</p>
              {track.origin && track.title !== track.origin.title && (
                <p className="truncate text-xs text-zinc-600">→ {track.title}</p>
              )}
            </div>
            <ProviderBadge provider={track.source} />
            {track.duplicate && (
              <span className="shrink-0 rounded-full bg-[#ff9f0a]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#ff9f0a]">
                In library
              </span>
            )}
          </div>
        )
      })}
    </Card>
  )
}
