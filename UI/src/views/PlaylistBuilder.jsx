import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, Checkbox, ErrorBox, Notice, PageHeader, Spinner, StatusIcon } from '../components/ui'
import Tutorial, { TutorialButton, useTutorial } from '../components/Tutorial'
import { useSetToggle } from '../hooks/useSetToggle'

function XmlHelp({ onClose }) {
  const [info, setInfo] = useState(null)

  useEffect(() => {
    call('rekordbox_xml_example').then(setInfo)
  }, [])

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-[15px] font-semibold text-zinc-100">What the file needs</h2>
          <p className="mt-1 text-[13px] text-zinc-500">Any XML with these two sections works. Everything else is ignored.</p>
        </div>
        <button onClick={onClose} className="text-xs text-[#0a84ff] hover:underline">
          Close
        </button>
      </div>
      {info && (
        <>
          <ul className="mt-4 flex flex-col gap-1.5 text-[13px] text-zinc-400">
            {info.rules.map((rule) => (
              <li key={rule} className="flex gap-2">
                <span className="text-zinc-600">•</span>
                <span>{rule}</span>
              </li>
            ))}
          </ul>
          <pre className="mt-4 overflow-x-auto rounded-xl bg-black/40 p-4 text-xs leading-relaxed text-zinc-300">{info.example}</pre>
          <p className="mt-3 text-xs text-zinc-600">
            .txt exports (tab separated, with a "Track Title" column) and folders of music are also accepted.
          </p>
        </>
      )}
    </Card>
  )
}

export default function PlaylistBuilder({ onBack }) {
  const [step, setStep] = useState('setup')
  const [sourcePath, setSourcePath] = useState(null)
  const [analysis, setAnalysis] = useState(null)
  const checked = useSetToggle()
  const expanded = useSetToggle()
  const tutorial = useTutorial()
  const [created, setCreated] = useState(0)
  const [error, setError] = useState(null)
  const [help, setHelp] = useState(false)
  const [armed, setArmed] = useState(false)

  const pickSource = async (mode) => {
    const path = await call('rekordbox_select_source', mode)
    if (path) setSourcePath(path)
  }

  const analyze = async () => {
    setError(null)
    setStep('analyzing')
    const result = await call('rekordbox_analyze', sourcePath)
    if (result.error) {
      setError(result.error)
      setStep('setup')
      return
    }
    setAnalysis(result)
    checked.replace(result.playlists.filter((p) => !p.exists && p.matched.length).map((p) => p.name))
    setStep('preview')
  }

  const create = async () => {
    if (!armed) {
      setArmed(true)
      return
    }
    setArmed(false)
    setError(null)
    setStep('creating')
    const result = await call('rekordbox_create', [...checked])
    if (result.error) {
      setError(result.error)
      setStep('preview')
      return
    }
    setCreated(result.created)
    setStep('done')
  }

  const reset = () => {
    setStep('setup')
    setSourcePath(null)
    setAnalysis(null)
    setError(null)
    setArmed(false)
  }

  const selectedTracks = analysis
    ? analysis.playlists.filter((p) => checked.has(p.name)).reduce((sum, p) => sum + p.matched.length, 0)
    : 0

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
      <PageHeader
        title="Playlist Builder"
        subtitle="Create RekordBox playlists from a file or a folder"
        onBack={onBack}
        action={<TutorialButton onClick={tutorial.toggle} open={tutorial.open} />}
      />
      <Tutorial id="builder" open={tutorial.open} onClose={tutorial.close} />

      {step === 'setup' && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <h2 className="text-[15px] font-semibold text-zinc-100">Playlist source</h2>
            <p className="mt-1.5 text-[13px] text-zinc-500">
              A playlist file (.xml or .txt), a folder of playlist files, or a folder of music.
            </p>
            <div className="mt-5 flex flex-wrap items-center gap-3">
              <Button variant="secondary" onClick={() => pickSource('file')}>
                Choose file
              </Button>
              <Button variant="secondary" onClick={() => pickSource('folder')}>
                Choose folder
              </Button>
              <button onClick={() => setHelp((v) => !v)} className="text-[13px] text-[#0a84ff] hover:underline">
                Which files work?
              </button>
            </div>
            {sourcePath && <p className="mt-4 truncate rounded-xl bg-black/40 px-4 py-3 text-xs text-zinc-400">{sourcePath}</p>}
          </Card>

          {help && <XmlHelp onClose={() => setHelp(false)} />}

          <ErrorBox>{error}</ErrorBox>

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
              {selectedTracks} tracks will be added · matched against {analysis.collection} tracks in your collection
            </p>
          </div>

          {analysis.running && <Notice>RekordBox is open. Close it before creating the playlists.</Notice>}

          <Card className="max-h-[440px] overflow-y-auto">
            {analysis.playlists.map((playlist, index) => {
              const selectable = !playlist.exists && playlist.matched.length > 0
              return (
                <div key={playlist.name} className={index > 0 ? 'border-t border-white/[0.05]' : ''}>
                  <div
                    onClick={() => selectable && checked.toggle(playlist.name)}
                    className={`flex items-center gap-4 px-5 py-3.5 transition-colors ${selectable ? 'cursor-pointer hover:bg-white/[0.04]' : 'opacity-50'}`}
                  >
                    <Checkbox checked={checked.has(playlist.name)} onChange={() => selectable && checked.toggle(playlist.name)} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm text-zinc-100">{playlist.name}</p>
                      <p className="text-xs text-zinc-600">
                        {playlist.matched.length} in your collection
                        {playlist.unmatched.length > 0 && ` · ${playlist.unmatched.length} not in RekordBox yet`}
                      </p>
                    </div>
                    {playlist.exists && (
                      <span className="rounded-full bg-white/[0.08] px-2.5 py-0.5 text-[11px] font-medium text-zinc-400">Already exists</span>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        expanded.toggle(playlist.name)
                      }}
                      className="text-zinc-500 transition-colors hover:text-zinc-200"
                      aria-label="Show tracks"
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
                          {track.title} <span className="opacity-60">({track.artist})</span> — not in RekordBox
                        </p>
                      ))}
                    </div>
                  )}
                </div>
              )
            })}
          </Card>

          {analysis.playlists.some((p) => p.unmatched.length) && (
            <Notice tone="info">
              Tracks marked "not in RekordBox" are skipped. Import them into RekordBox first, or use the Synchronizer with the music folder.
            </Notice>
          )}

          <ErrorBox>{error}</ErrorBox>

          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={reset}>
              Back
            </Button>
            <div className="flex items-center gap-3">
              {armed && <span className="text-xs text-[#ff9f0a]">This writes to your RekordBox database.</span>}
              <Button onClick={create} disabled={!checked.size || analysis.running}>
                {armed ? 'Confirm' : `Create ${checked.size} ${checked.size === 1 ? 'playlist' : 'playlists'}`}
              </Button>
            </div>
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
          <Button className="mt-6" onClick={reset}>
            New import
          </Button>
        </div>
      )}
    </div>
  )
}
