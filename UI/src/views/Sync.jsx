import { useEffect, useRef, useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, Checkbox, StatusIcon } from '../components/ui'
import DownloadRunner from '../components/DownloadRunner'

export default function Sync({ onBack }) {
  const [step, setStep] = useState('setup')
  const [ready, setReady] = useState(null)
  const [url, setUrl] = useState('')
  const [folder, setFolder] = useState(null)
  const [status, setStatus] = useState(null)
  const [orphanChecked, setOrphanChecked] = useState(new Set())
  const [missingChecked, setMissingChecked] = useState(new Set())
  const [deleteArmed, setDeleteArmed] = useState(false)
  const [deleteResults, setDeleteResults] = useState(null)
  const [error, setError] = useState(null)
  const pollRef = useRef(null)

  useEffect(() => {
    call('spotify_ready').then(setReady)
    return () => clearInterval(pollRef.current)
  }, [])

  const pickFolder = async () => {
    const path = await call('select_folder')
    if (path) setFolder(path)
  }

  const analyze = async () => {
    setError(null)
    setDeleteResults(null)
    setDeleteArmed(false)
    setStep('analyzing')
    setStatus(null)
    await call('start_sync_analysis', url.trim(), folder)
    pollRef.current = setInterval(async () => {
      const s = await call('get_sync_status')
      setStatus(s)
      if (!s.running) {
        clearInterval(pollRef.current)
        if (s.error) {
          setError(s.error)
          setStep('setup')
        } else {
          setOrphanChecked(new Set())
          setMissingChecked(new Set(s.missing.filter((m) => m.video).map((m) => m.spotify_id)))
          setStep('results')
        }
      }
    }, 700)
  }

  const deleteOrphans = async () => {
    if (!deleteArmed) {
      setDeleteArmed(true)
      return
    }
    setDeleteArmed(false)
    const paths = status.orphans.filter((o) => orphanChecked.has(o.path)).map((o) => o.path)
    const results = await call('sync_delete', paths)
    setDeleteResults(results)
    setStatus((prev) => ({
      ...prev,
      orphans: prev.orphans.filter((o) => !results.some((r) => r.ok && r.path === o.path)),
    }))
    setOrphanChecked(new Set())
  }

  const reset = () => {
    setStep('setup')
    setStatus(null)
    setError(null)
    setDeleteResults(null)
    setDeleteArmed(false)
  }

  const missingWithVideo = status?.missing.filter((m) => m.video) ?? []
  const missingNotFound = status?.missing.filter((m) => !m.video) ?? []

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
          <h1 className="text-xl font-semibold text-white">Playlist Sync</h1>
          <p className="text-[13px] text-zinc-500">Spotify playlist as the source of truth</p>
        </div>
      </header>

      {step === 'setup' && ready && !ready.ready && (
        <Card className="p-6">
          <h2 className="text-[15px] font-semibold text-zinc-100">Spotify credentials required</h2>
          <p className="mt-2 text-sm text-zinc-400">
            Set up your credentials in the Spotify Converter first, then come back here.
          </p>
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
              placeholder="https://open.spotify.com/playlist/..."
              className="w-full rounded-xl border border-white/[0.1] bg-black/40 px-4 py-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none transition-colors focus:border-[#0a84ff]"
            />
          </Card>

          <Card className="p-6">
            <h2 className="text-[13px] font-medium text-zinc-400">Local folder to sync</h2>
            <div className="mt-3 flex items-center gap-3">
              <Button variant="secondary" onClick={pickFolder}>
                Choose folder
              </Button>
              {folder && <p className="min-w-0 flex-1 truncate text-xs text-zinc-400">{folder}</p>}
            </div>
          </Card>

          {error && (
            <div className="rounded-xl border border-[#ff453a]/30 bg-[#ff453a]/10 px-4 py-3 text-sm text-[#ff6961]">
              {error}
            </div>
          )}

          <Button onClick={analyze} disabled={!url.trim() || !folder} className="self-end">
            Compare
          </Button>
        </div>
      )}

      {step === 'analyzing' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <div className="mb-3 flex items-center justify-between text-sm">
              <span className="font-medium text-zinc-200">
                {!status?.phase || status.phase === 'fetching'
                  ? 'Fetching playlist from Spotify...'
                  : status.phase === 'comparing'
                    ? 'Comparing with local folder...'
                    : `Finding YouTube equivalents for missing tracks`}
              </span>
              {status?.phase === 'matching' && status.total > 0 && (
                <span className="text-zinc-500">
                  {status.processed} / {status.total}
                </span>
              )}
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
              <div
                className="h-full rounded-full bg-[#30d158] transition-all duration-500"
                style={{
                  width:
                    status?.phase === 'matching' && status.total > 0
                      ? `${(status.processed / status.total) * 100}%`
                      : '10%',
                }}
              />
            </div>
          </Card>
        </div>
      )}

      {step === 'results' && status && (
        <div className="flex flex-col gap-5">
          <div className="flex items-end justify-between">
            <div>
              <h2 className="text-lg font-semibold text-white">{status.playlist}</h2>
              <p className="text-[13px] text-zinc-500">
                {status.in_sync} in sync · {status.missing.length} missing locally · {status.orphans.length} local orphans
              </p>
            </div>
            <Button variant="ghost" onClick={reset}>
              New sync
            </Button>
          </div>

          {status.orphans.length === 0 && status.missing.length === 0 && (
            <div className="flex flex-col items-center py-10 text-center">
              <StatusIcon ok />
              <h3 className="mt-4 text-lg font-semibold text-white">Everything in sync</h3>
              <p className="mt-1 text-[13px] text-zinc-500">The folder matches the Spotify playlist.</p>
            </div>
          )}

          {status.orphans.length > 0 && (
            <Card className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
                <span className="text-[13px] font-medium text-zinc-200">
                  Local files not in the playlist
                </span>
                <span className="text-xs text-zinc-500">{orphanChecked.size} selected</span>
              </div>
              <div className="max-h-[240px] overflow-y-auto">
                {status.orphans.map((orphan) => (
                  <div
                    key={orphan.path}
                    onClick={() =>
                      setOrphanChecked((prev) => {
                        const next = new Set(prev)
                        next.has(orphan.path) ? next.delete(orphan.path) : next.add(orphan.path)
                        return next
                      })
                    }
                    className="flex cursor-pointer items-center gap-4 border-t border-white/[0.05] px-5 py-3 transition-colors first:border-t-0 hover:bg-white/[0.04]"
                  >
                    <Checkbox
                      checked={orphanChecked.has(orphan.path)}
                      onChange={() =>
                        setOrphanChecked((prev) => {
                          const next = new Set(prev)
                          next.has(orphan.path) ? next.delete(orphan.path) : next.add(orphan.path)
                          return next
                        })
                      }
                    />
                    <span className="flex-1 truncate text-sm text-zinc-300">{orphan.filename}</span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-end gap-3 border-t border-white/[0.06] px-5 py-3">
                {deleteArmed && <span className="text-xs text-[#ff6961]">This permanently deletes the files.</span>}
                <Button variant="danger" onClick={deleteOrphans} disabled={!orphanChecked.size}>
                  {deleteArmed ? `Confirm delete ${orphanChecked.size}` : `Delete ${orphanChecked.size || ''} selected`}
                </Button>
              </div>
            </Card>
          )}

          {deleteResults && (
            <div className="rounded-xl border border-white/[0.08] bg-white/[0.04] px-4 py-3 text-sm text-zinc-400">
              {deleteResults.filter((r) => r.ok).length} file(s) deleted
              {deleteResults.some((r) => !r.ok) && (
                <span className="text-[#ff6961]"> · {deleteResults.filter((r) => !r.ok).length} failed</span>
              )}
            </div>
          )}

          {status.missing.length > 0 && (
            <Card className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
                <span className="text-[13px] font-medium text-zinc-200">Missing locally</span>
                <span className="text-xs text-zinc-500">{missingChecked.size} selected</span>
              </div>
              <div className="max-h-[280px] overflow-y-auto">
                {missingWithVideo.map((track) => (
                  <div
                    key={track.spotify_id}
                    onClick={() =>
                      setMissingChecked((prev) => {
                        const next = new Set(prev)
                        next.has(track.spotify_id) ? next.delete(track.spotify_id) : next.add(track.spotify_id)
                        return next
                      })
                    }
                    className="flex cursor-pointer items-center gap-4 border-t border-white/[0.05] px-5 py-3 transition-colors first:border-t-0 hover:bg-white/[0.04]"
                  >
                    <Checkbox
                      checked={missingChecked.has(track.spotify_id)}
                      onChange={() =>
                        setMissingChecked((prev) => {
                          const next = new Set(prev)
                          next.has(track.spotify_id) ? next.delete(track.spotify_id) : next.add(track.spotify_id)
                          return next
                        })
                      }
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-zinc-300">
                        {track.artists.join(', ')} - {track.title}
                      </p>
                      <p className="truncate text-xs text-zinc-600">→ {track.video.title}</p>
                    </div>
                  </div>
                ))}
                {missingNotFound.map((track) => (
                  <div key={track.spotify_id} className="flex items-center gap-4 border-t border-white/[0.05] px-5 py-3 opacity-50">
                    <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center">
                      <span className="h-2 w-2 rounded-full bg-[#ff9f0a]" />
                    </span>
                    <span className="flex-1 truncate text-sm text-zinc-400">
                      {track.artists.join(', ')} - {track.title}
                    </span>
                    <span className="rounded-full bg-[#ff9f0a]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#ff9f0a]">
                      Not found
                    </span>
                  </div>
                ))}
              </div>
              <div className="flex items-center justify-end border-t border-white/[0.06] px-5 py-3">
                <Button onClick={() => setStep('downloading')} disabled={!missingChecked.size}>
                  Download {missingChecked.size} {missingChecked.size === 1 ? 'track' : 'tracks'}
                </Button>
              </div>
            </Card>
          )}
        </div>
      )}

      {step === 'downloading' && status && (
        <DownloadRunner
          videos={missingWithVideo
            .filter((m) => missingChecked.has(m.spotify_id))
            .map((m) => m.video)}
          playlistName={null}
          outputDirectory={status.folder}
          operation="sync"
          onReset={reset}
          resetLabel="Back to sync"
        />
      )}
    </div>
  )
}
