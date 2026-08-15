import { useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, Checkbox, StatusIcon } from '../components/ui'

export default function Rekordbox({ onBack }) {
  const [step, setStep] = useState('setup')
  const [sourcePath, setSourcePath] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const [checked, setChecked] = useState(new Set())
  const [expanded, setExpanded] = useState(new Set())
  const [created, setCreated] = useState(0)
  const [error, setError] = useState(null)

  const pickSource = async (mode) => {
    const path = await call('rekordbox_select_source', mode)
    if (path) setSourcePath(path)
  }

  const analyze = async () => {
    setError(null)
    setStep('analyzing')
    try {
      const result = await call('rekordbox_analyze', sourcePath)
      if (result.error) throw new Error(result.error)
      setAnalysis(result)
      setChecked(new Set(result.playlists.filter((p) => !p.exists && p.matched.length).map((p) => p.name)))
      setStep('preview')
    } catch (err) {
      setError(String(err?.message || err))
      setStep('setup')
    }
  }

  const create = async () => {
    setError(null)
    setStep('creating')
    try {
      const result = await call('rekordbox_create', [...checked])
      if (result.error) throw new Error(result.error)
      setCreated(result.created)
      setStep('done')
    } catch (err) {
      setError(String(err?.message || err))
      setStep('preview')
    }
  }

  const togglePlaylist = (name) =>
    setChecked((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })

  const toggleExpanded = (name) =>
    setExpanded((prev) => {
      const next = new Set(prev)
      next.has(name) ? next.delete(name) : next.add(name)
      return next
    })

  const reset = () => {
    setStep('setup')
    setSourcePath(null)
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
          <h1 className="text-xl font-semibold text-white">RekordBox Playlists</h1>
          <p className="text-[13px] text-zinc-500">Rebuild playlists from .txt or .xml exports</p>
        </div>
      </header>

      {step === 'setup' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <h2 className="text-[15px] font-semibold text-zinc-100">Playlist source</h2>
            <p className="mt-1.5 text-[13px] text-zinc-500">
              Pick a playlist export (.txt / .xml), a folder of exports, or a downloaded music folder.
            </p>
            <div className="mt-5 flex gap-3">
              <Button variant="secondary" onClick={() => pickSource('file')}>
                Choose file
              </Button>
              <Button variant="secondary" onClick={() => pickSource('folder')}>
                Choose folder
              </Button>
            </div>
            {sourcePath && (
              <p className="mt-4 truncate rounded-xl bg-black/40 px-4 py-3 text-xs text-zinc-400">{sourcePath}</p>
            )}
          </Card>

          {error && (
            <div className="rounded-xl border border-[#ff453a]/30 bg-[#ff453a]/10 px-4 py-3 text-sm text-[#ff6961]">
              {error}
            </div>
          )}

          <Button onClick={analyze} disabled={!sourcePath} className="self-end">
            Continue
          </Button>
        </div>
      )}

      {step === 'analyzing' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 pb-24">
          <Spinner className="h-8 w-8" />
          <p className="text-sm text-zinc-400">Matching against your RekordBox collection...</p>
        </div>
      )}

      {step === 'preview' && analysis && (
        <div className="flex flex-col gap-5">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {checked.size} of {analysis.playlists.length} playlists selected
            </h2>
            <p className="text-[13px] text-zinc-500">
              Matched against {analysis.collection} tracks in your collection
            </p>
          </div>

          {analysis.running && (
            <div className="rounded-xl border border-[#ff9f0a]/30 bg-[#ff9f0a]/10 px-4 py-3 text-sm text-[#ff9f0a]">
              RekordBox is open. Close it before creating the playlists.
            </div>
          )}

          <Card className="max-h-[440px] overflow-y-auto">
            {analysis.playlists.map((playlist, index) => {
              const selectable = !playlist.exists && playlist.matched.length > 0
              return (
                <div key={playlist.name} className={index > 0 ? 'border-t border-white/[0.05]' : ''}>
                  <div
                    onClick={() => selectable && togglePlaylist(playlist.name)}
                    className={`flex items-center gap-4 px-5 py-3.5 transition-colors ${
                      selectable ? 'cursor-pointer hover:bg-white/[0.04]' : 'opacity-50'
                    }`}
                  >
                    <Checkbox
                      checked={checked.has(playlist.name)}
                      onChange={() => selectable && togglePlaylist(playlist.name)}
                    />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-zinc-100">{playlist.name}</p>
                      <p className="text-xs text-zinc-600">
                        {playlist.matched.length} matched
                        {playlist.unmatched.length > 0 && ` · ${playlist.unmatched.length} not found`}
                      </p>
                    </div>
                    {playlist.exists && (
                      <span className="rounded-full bg-white/[0.08] px-2.5 py-0.5 text-[11px] font-medium text-zinc-400">
                        Already exists
                      </span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        toggleExpanded(playlist.name)
                      }}
                      className="text-zinc-500 transition-colors hover:text-zinc-200"
                    >
                      <svg
                        viewBox="0 0 24 24"
                        className={`h-4 w-4 fill-none stroke-current transition-transform ${expanded.has(playlist.name) ? 'rotate-180' : ''}`}
                        strokeWidth="2"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <path d="M6 9l6 6 6-6" />
                      </svg>
                    </button>
                  </div>
                  {expanded.has(playlist.name) && (
                    <div className="border-t border-white/[0.04] bg-black/20 px-5 py-3">
                      {playlist.matched.map((track, i) => (
                        <p key={`m${i}`} className="truncate py-0.5 text-xs text-zinc-400">
                          {track.title} <span className="text-zinc-600">({track.artist})</span>
                        </p>
                      ))}
                      {playlist.unmatched.map((track, i) => (
                        <p key={`u${i}`} className="truncate py-0.5 text-xs text-[#ff9f0a]/80">
                          {track.title} <span className="opacity-60">({track.artist})</span> — not found
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </Card>

          {error && (
            <div className="rounded-xl border border-[#ff453a]/30 bg-[#ff453a]/10 px-4 py-3 text-sm text-[#ff6961]">
              {error}
            </div>
          )}

          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={reset}>
              Back
            </Button>
            <Button onClick={create} disabled={!checked.size}>
              Create {checked.size} {checked.size === 1 ? 'playlist' : 'playlists'}
            </Button>
          </div>
        </div>
      )}

      {step === 'creating' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 pb-24">
          <Spinner className="h-8 w-8" />
          <p className="text-sm text-zinc-400">Writing to the RekordBox database...</p>
        </div>
      )}

      {step === 'done' && (
        <div className="flex flex-col items-center py-12 text-center">
          <StatusIcon ok />
          <h2 className="mt-4 text-xl font-semibold text-white">
            {created} {created === 1 ? 'playlist' : 'playlists'} created
          </h2>
          <p className="mt-1 text-[13px] text-zinc-500">Open RekordBox to see them in your playlist tree.</p>
          <div className="mt-6 flex gap-3">
            <Button onClick={reset}>New import</Button>
          </div>
        </div>
      )}
    </div>
  )
}
