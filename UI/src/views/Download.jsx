import { useEffect, useRef, useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, Toggle, Checkbox, StatusIcon } from '../components/ui'

export default function Download({ onBack }) {
  const [step, setStep] = useState('setup')
  const [url, setUrl] = useState('')
  const [scanEnabled, setScanEnabled] = useState(false)
  const [folders, setFolders] = useState([])
  const [selectedFolders, setSelectedFolders] = useState(new Set(['__all__']))
  const [analysis, setAnalysis] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [status, setStatus] = useState(null)
  const [outputDir, setOutputDir] = useState(null)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    if (scanEnabled) call('list_download_folders').then(setFolders)
  }, [scanEnabled])

  useEffect(() => () => clearInterval(pollRef.current), [])

  const toggleFolder = (name) => {
    setSelectedFolders((prev) => {
      const next = new Set(prev)
      if (name === '__all__') return new Set(['__all__'])
      next.delete('__all__')
      next.has(name) ? next.delete(name) : next.add(name)
      return next.size ? next : new Set(['__all__'])
    })
  }

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

  const startDownload = async () => {
    const videos = analysis.videos.filter((v) => checked.has(v.id))
    const dir = await call('start_download', videos, analysis.playlist)
    setOutputDir(dir)
    setStep('downloading')
    pollRef.current = setInterval(async () => {
      const s = await call('get_status')
      setStatus(s)
      if (!s.running && s.items.length >= videos.length) {
        clearInterval(pollRef.current)
        setStep('done')
      }
    }, 800)
  }

  const reset = () => {
    setStep('setup')
    setUrl('')
    setAnalysis(null)
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

          <Card className="p-6">
            <Toggle checked={scanEnabled} onChange={setScanEnabled} label="Scan Downloads for duplicates" />
            {scanEnabled && (
              <div className="mt-5 flex flex-col gap-1 border-t border-white/[0.06] pt-4">
                <FolderRow
                  name="All folders"
                  checked={selectedFolders.has('__all__')}
                  onToggle={() => toggleFolder('__all__')}
                />
                {folders.map((name) => (
                  <FolderRow
                    key={name}
                    name={name}
                    checked={selectedFolders.has(name)}
                    onToggle={() => toggleFolder(name)}
                  />
                ))}
              </div>
            )}
          </Card>

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
              <h2 className="text-lg font-semibold text-white">
                {analysis.playlist || 'Single video'}
              </h2>
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
                onClick={() =>
                  setChecked((prev) => {
                    const next = new Set(prev)
                    next.has(video.id) ? next.delete(video.id) : next.add(video.id)
                    return next
                  })
                }
                className={`flex cursor-pointer items-center gap-4 px-5 py-3.5 transition-colors hover:bg-white/[0.04] ${
                  index > 0 ? 'border-t border-white/[0.05]' : ''
                }`}
              >
                <Checkbox
                  checked={checked.has(video.id)}
                  onChange={() =>
                    setChecked((prev) => {
                      const next = new Set(prev)
                      next.has(video.id) ? next.delete(video.id) : next.add(video.id)
                      return next
                    })
                  }
                />
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
            <Button onClick={startDownload} disabled={!checked.size}>
              Download {checked.size} {checked.size === 1 ? 'track' : 'tracks'}
            </Button>
          </div>
        </div>
      )}

      {step === 'downloading' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <div className="mb-3 flex items-center justify-between text-sm">
              <span className="font-medium text-zinc-200">Downloading</span>
              <span className="text-zinc-500">
                {status?.items.length ?? 0} / {status?.total ?? '...'}
              </span>
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
              <div
                className="h-full rounded-full bg-[#0a84ff] transition-all duration-500"
                style={{ width: `${status?.total ? (status.items.length / status.total) * 100 : 0}%` }}
              />
            </div>
            {status?.current && (
              <p className="mt-4 flex items-center gap-2.5 text-sm text-zinc-400">
                <Spinner className="h-4 w-4" />
                <span className="truncate">{status.current}</span>
              </p>
            )}
          </Card>

          {status?.items.length > 0 && (
            <Card className="max-h-[340px] overflow-y-auto">
              {[...status.items].reverse().map((item, index) => (
                <div
                  key={item.id}
                  className={`flex items-center gap-4 px-5 py-3 ${index > 0 ? 'border-t border-white/[0.05]' : ''}`}
                >
                  <StatusIcon ok={item.ok} />
                  <span className="flex-1 truncate text-sm text-zinc-300">{item.title}</span>
                </div>
              ))}
            </Card>
          )}
        </div>
      )}

      {step === 'done' && status && (
        <div className="flex flex-col gap-5">
          <div className="flex flex-col items-center py-8 text-center">
            <StatusIcon ok={!status.items.some((i) => !i.ok)} />
            <h2 className="mt-4 text-xl font-semibold text-white">
              {status.items.filter((i) => i.ok).length} of {status.total} tracks downloaded
            </h2>
            <p className="mt-1 text-[13px] text-zinc-500">{outputDir}</p>
          </div>

          {status.items.some((i) => !i.ok) && (
            <Card className="max-h-[280px] overflow-y-auto">
              <div className="border-b border-white/[0.06] px-5 py-3 text-[13px] font-medium text-[#ff6961]">
                Failed downloads
              </div>
              {status.items.filter((i) => !i.ok).map((item) => (
                <div key={item.id} className="border-t border-white/[0.05] px-5 py-3 first:border-t-0">
                  <p className="truncate text-sm text-zinc-300">{item.title}</p>
                  <p className="truncate text-xs text-zinc-600">{item.url}</p>
                </div>
              ))}
            </Card>
          )}

          <div className="flex items-center justify-center gap-3">
            <Button variant="secondary" onClick={() => call('open_output_directory')}>
              Open folder
            </Button>
            <Button onClick={reset}>New download</Button>
          </div>
        </div>
      )}
    </div>
  )
}

function FolderRow({ name, checked, onToggle }) {
  return (
    <div
      onClick={onToggle}
      className="flex cursor-pointer items-center gap-3 rounded-lg px-2 py-2 transition-colors hover:bg-white/[0.04]"
    >
      <Checkbox checked={checked} onChange={onToggle} />
      <span className="text-sm text-zinc-300">{name}</span>
    </div>
  )
}
