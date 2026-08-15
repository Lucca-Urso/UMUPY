import { useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, Checkbox } from '../components/ui'
import ScanFolders from '../components/ScanFolders'
import DownloadRunner from '../components/DownloadRunner'

export default function Download({ onBack }) {
  const [step, setStep] = useState('setup')
  const [url, setUrl] = useState('')
  const [scanEnabled, setScanEnabled] = useState(false)
  const [selectedFolders, setSelectedFolders] = useState(new Set(['__all__']))
  const [analysis, setAnalysis] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [error, setError] = useState(null)

  const analyze = async () => {
    setError(null)
    setStep('analyzing')
    try {
      const result = await call('analyze_url', url.trim(), scanEnabled ? [...selectedFolders] : null)
      if (!result.ffmpeg) throw new Error('FFmpeg not found. Install it globally or place it in Dependencies/.')
      if (!result.videos.length) throw new Error('No downloadable content found at this URL.')
      setAnalysis(result)
      setChecked(new Set(result.videos.filter((v) => !v.duplicate).map((v) => v.id)))
      setStep('select')
    } catch (err) {
      setError(String(err?.message || err))
      setStep('setup')
    }
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
    setAnalysis(null)
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
          <h1 className="text-xl font-semibold text-white">YouTube Downloader</h1>
          <p className="text-[13px] text-zinc-500">MP3 with embedded artwork</p>
        </div>
      </header>

      {step === 'setup' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <label className="mb-2 block text-[13px] font-medium text-zinc-400">Video or playlist URL</label>
            <input
              autoFocus
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && url.trim() && analyze()}
              placeholder="https://www.youtube.com/..."
              className="w-full rounded-xl border border-white/[0.1] bg-black/40 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-[#0a84ff]"
            />
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

      {step === 'analyzing' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 pb-24">
          <Spinner className="h-8 w-8" />
          <p className="text-sm text-zinc-400">Checking content...</p>
          <p className="text-xs text-zinc-600">Large playlists can take a moment</p>
        </div>
      )}

      {step === 'select' && analysis && (
        <div className="flex flex-col gap-5">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">{analysis.playlist || 'Single video'}</h2>
              <p className="text-[13px] text-zinc-500">
                {checked.size} of {analysis.videos.length} tracks selected
              </p>
            </div>
            <div className="flex gap-2 text-[13px]">
              <button onClick={() => setChecked(new Set(analysis.videos.map((v) => v.id)))} className="text-[#0a84ff] hover:underline">
                Select all
              </button>
              <span className="text-zinc-700">·</span>
              <button onClick={() => setChecked(new Set())} className="text-[#0a84ff] hover:underline">
                Clear
              </button>
            </div>
          </div>

          <Card className="max-h-[420px] overflow-y-auto">
            {analysis.videos.map((video, index) => (
              <div
                key={video.id}
                onClick={() => toggleVideo(video.id)}
                className={`flex cursor-pointer items-center gap-4 px-5 py-3.5 transition-colors hover:bg-white/[0.04] ${
                  index > 0 ? 'border-t border-white/[0.05]' : ''
                }`}
              >
                <Checkbox checked={checked.has(video.id)} onChange={() => toggleVideo(video.id)} />
                <span className={`flex-1 truncate text-sm ${checked.has(video.id) ? 'text-zinc-100' : 'text-zinc-500'}`}>
                  {video.title}
                </span>
                {video.duplicate && (
                  <span className="rounded-full bg-[#ff9f0a]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#ff9f0a]">
                    Duplicate
                  </span>
                )}
              </div>
            ))}
          </Card>

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

      {step === 'downloading' && analysis && (
        <DownloadRunner
          videos={analysis.videos.filter((v) => checked.has(v.id))}
          playlistName={analysis.playlist}
          onReset={reset}
        />
      )}
    </div>
  )
}
