import { useEffect, useRef, useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, Checkbox } from '../components/ui'
import ScanFolders from '../components/ScanFolders'
import DownloadRunner from '../components/DownloadRunner'

export default function Spotify({ onBack }) {
  const [step, setStep] = useState('setup')
  const [ready, setReady] = useState(null)
  const [url, setUrl] = useState('')
  const [scanEnabled, setScanEnabled] = useState(false)
  const [selectedFolders, setSelectedFolders] = useState(new Set(['__all__']))
  const [status, setStatus] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    call('spotify_ready').then(setReady)
    return () => clearInterval(pollRef.current)
  }, [])

  const analyze = async () => {
    setError(null)
    setStep('matching')
    setStatus(null)
    await call('start_spotify_analysis', url.trim(), scanEnabled ? [...selectedFolders] : null)
    pollRef.current = setInterval(async () => {
      const s = await call('get_spotify_status')
      setStatus(s)
      if (!s.running) {
        clearInterval(pollRef.current)
        if (s.error) {
          setError(s.error)
          setStep('setup')
        } else if (!s.matched.length) {
          setError('No YouTube equivalents found for this playlist.')
          setStep('setup')
        } else {
          setChecked(new Set(s.matched.filter((v) => !v.duplicate).map((v) => v.id)))
          setStep('select')
        }
      }
    }, 700)
  }

  const toggleVideo = (id) =>
    setChecked((prev) => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })

  const reset = () => {
    setStep('setup')
    setUrl('')
    setStatus(null)
    setError(null)
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
      <header className="flex items-center gap-3 pt-8 pb-10">
        <button
          onClick={onBack}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.06] text-zinc-400 transition-colors hover:bg-white/[0.12] hover:text-white"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </button>
        <div>
          <h1 className="text-xl font-semibold text-white">Spotify Converter</h1>
          <p className="text-[13px] text-zinc-500">From Spotify playlist to YouTube downloads</p>
        </div>
      </header>

      {step === 'setup' && ready && !ready.ready && (
        <Card className="p-6">
          <h2 className="text-[15px] font-semibold text-zinc-100">Connect your Spotify account</h2>
          <p className="mt-2 text-sm leading-relaxed text-zinc-400">
            1. Create a free app at{' '}
            <span className="text-[#0a84ff]">developer.spotify.com/dashboard</span> with redirect URI{' '}
            <code className="rounded bg-black/40 px-1.5 py-0.5 text-xs">http://127.0.0.1:8888/callback</code>
          </p>
          <p className="mt-2 text-sm text-zinc-400">2. Save your credentials as:</p>
          <pre className="mt-2 overflow-x-auto rounded-xl bg-black/40 p-4 text-xs text-zinc-300">
{`// ${ready.path}
{"client_id": "...", "client_secret": "...",
 "redirect_uri": "http://127.0.0.1:8888/callback"}`}
          </pre>
          <Button className="mt-4" onClick={() => call('spotify_ready').then(setReady)}>
            Check again
          </Button>
        </Card>
      )}

      {step === 'setup' && ready?.ready && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <label className="mb-2 block text-[13px] font-medium text-zinc-400">Spotify playlist URL</label>
            <input
              autoFocus
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && url.trim() && analyze()}
              placeholder="https://open.spotify.com/playlist/..."
              className="w-full rounded-xl border border-white/[0.1] bg-black/40 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-[#0a84ff]"
            />
            <p className="mt-3 text-xs text-zinc-600">
              First conversion opens the browser once for Spotify login.
            </p>
          </Card>

          <ScanFolders
            enabled={scanEnabled}
            onEnabledChange={setScanEnabled}
            selection={selectedFolders}
            onSelectionChange={setSelectedFolders}
          />

          {error && (
            <div className="rounded-xl border border-[#ff453a]/30 bg-[#ff453a]/10 px-4 py-3 text-sm text-[#ff6961]">
              {error}
            </div>
          )}

          <Button onClick={analyze} disabled={!url.trim()} className="self-end">
            Continue
          </Button>
        </div>
      )}

      {step === 'matching' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <div className="mb-3 flex items-center justify-between text-sm">
              <span className="font-medium text-zinc-200">
                {status?.phase === 'matching'
                  ? `Matching "${status.playlist}"`
                  : 'Fetching playlist from Spotify...'}
              </span>
              {status?.phase === 'matching' && (
                <span className="text-zinc-500">
                  {status.processed} / {status.total}
                </span>
              )}
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
              <div
                className="h-full rounded-full bg-[#30d158] transition-all duration-500"
                style={{ width: `${status?.total ? (status.processed / status.total) * 100 : 0}%` }}
              />
            </div>
          </Card>

          {status?.matched.length > 0 && (
            <Card className="max-h-[380px] overflow-y-auto">
              {[...status.matched].reverse().map((video, index) => (
                <div
                  key={video.id}
                  className={`px-5 py-3 ${index > 0 ? 'border-t border-white/[0.05]' : ''}`}
                >
                  <p className="truncate text-sm text-zinc-300">
                    {video.source.artists.join(', ')} - {video.source.title}
                  </p>
                  <p className="truncate text-xs text-zinc-600">→ {video.title}</p>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}

      {step === 'select' && status && (
        <div className="flex flex-col gap-5">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">{status.playlist}</h2>
              <p className="text-[13px] text-zinc-500">
                {checked.size} of {status.matched.length} matches selected
                {status.unmatched.length > 0 && ` · ${status.unmatched.length} not found`}
              </p>
            </div>
            <div className="flex gap-2 text-[13px]">
              <button onClick={() => setChecked(new Set(status.matched.map((v) => v.id)))} className="text-[#0a84ff] hover:underline">
                Select all
              </button>
              <span className="text-zinc-700">·</span>
              <button onClick={() => setChecked(new Set())} className="text-[#0a84ff] hover:underline">
                Clear
              </button>
            </div>
          </div>

          <Card className="max-h-[380px] overflow-y-auto">
            {status.matched.map((video, index) => (
              <div
                key={video.id}
                onClick={() => toggleVideo(video.id)}
                className={`flex cursor-pointer items-center gap-4 px-5 py-3 transition-colors hover:bg-white/[0.04] ${
                  index > 0 ? 'border-t border-white/[0.05]' : ''
                }`}
              >
                <Checkbox checked={checked.has(video.id)} onChange={() => toggleVideo(video.id)} />
                <div className="min-w-0 flex-1">
                  <p className={`truncate text-sm ${checked.has(video.id) ? 'text-zinc-100' : 'text-zinc-500'}`}>
                    {video.source.artists.join(', ')} - {video.source.title}
                  </p>
                  <p className="truncate text-xs text-zinc-600">→ {video.title}</p>
                </div>
                {video.duplicate && (
                  <span className="rounded-full bg-[#ff9f0a]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#ff9f0a]">
                    Duplicate
                  </span>
                )}
              </div>
            ))}
          </Card>

          {status.unmatched.length > 0 && (
            <Card className="max-h-[200px] overflow-y-auto">
              <div className="border-b border-white/[0.06] px-5 py-3 text-[13px] font-medium text-[#ff9f0a]">
                Not found on YouTube Music
              </div>
              {status.unmatched.map((track, index) => (
                <div key={index} className="border-t border-white/[0.05] px-5 py-2.5 first:border-t-0">
                  <p className="truncate text-sm text-zinc-500">
                    {track.artists.join(', ')} - {track.title}
                  </p>
                </div>
              ))}
            </Card>
          )}

          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={reset}>
              Back
            </Button>
            <Button onClick={() => setStep('downloading')} disabled={!checked.size}>
              Download {checked.size} {checked.size === 1 ? 'track' : 'tracks'}
            </Button>
          </div>
        </div>
      )}

      {step === 'downloading' && status && (
        <DownloadRunner
          videos={status.matched.filter((v) => checked.has(v.id))}
          playlistName={status.playlist}
          onReset={reset}
          resetLabel="New conversion"
        />
      )}
    </div>
  )
}
