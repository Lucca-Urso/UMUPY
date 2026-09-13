import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, ErrorBox, Notice, PageHeader, ProgressCard, SelectionHeader } from '../components/ui'
import LinkList, { detectProvider } from '../components/LinkList'
import TrackList from '../components/TrackList'
import ScanFolders from '../components/ScanFolders'
import DownloadRunner from '../components/DownloadRunner'
import Tutorial, { TutorialButton, useTutorial } from '../components/Tutorial'
import { usePolling } from '../hooks/usePolling'
import { useSetToggle } from '../hooks/useSetToggle'
import { useSpotifyReady } from '../hooks/useSpotifyReady'

export default function Downloader({ onBack, onSetup }) {
  const [step, setStep] = useState('setup')
  const [links, setLinks] = useState([''])
  const [scanEnabled, setScanEnabled] = useState(false)
  const [selectedFolders, setSelectedFolders] = useState(new Set(['__all__']))
  const checked = useSetToggle()
  const [error, setError] = useState(null)
  const [showDuplicates, setShowDuplicates] = useState(false)
  const [spotify] = useSpotifyReady()
  const [status] = usePolling('get_analysis_status', step === 'analyzing')
  const tutorial = useTutorial()

  const validLinks = links.map((l) => l.trim()).filter((l) => l && detectProvider(l))
  const needsSpotify = validLinks.some((l) => detectProvider(l) === 'spotify') && spotify && !spotify.ready

  useEffect(() => {
    if (step !== 'analyzing' || !status || status.running) return
    if (status.error) {
      setError(status.error)
      setStep('setup')
    } else if (!status.matched.length) {
      setError('No downloadable tracks were found for these links.')
      setStep('setup')
    } else {
      checked.replace(status.matched.filter((v) => !v.duplicate).map((v) => v.id))
      setStep('select')
    }
  }, [status, step])

  const analyze = async () => {
    setError(null)
    setStep('analyzing')
    await call('start_analysis', validLinks, scanEnabled ? [...selectedFolders] : null)
  }

  const reset = () => {
    setStep('setup')
    setLinks([''])
    setError(null)
  }

  const operation = validLinks.every((l) => detectProvider(l) === 'youtube') ? 'youtube' : 'spotify'
  const fresh = status?.matched.filter((v) => !v.duplicate) ?? []
  const duplicates = status?.matched.filter((v) => v.duplicate) ?? []
  const duplicateIds = new Set(duplicates.map((v) => v.id))

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
      <PageHeader
        title="Downloader"
        subtitle="MP3 with embedded artwork from YouTube, Spotify or SoundCloud"
        onBack={onBack}
        action={<TutorialButton onClick={tutorial.toggle} open={tutorial.open} />}
      />
      <Tutorial id="downloader" open={tutorial.open} onClose={tutorial.close} />

      {step === 'setup' && (
        <div className="flex flex-col gap-5">
          <LinkList links={links} onChange={setLinks} placeholder="https://open.spotify.com/playlist/... or youtube.com/... or soundcloud.com/..." />

          {needsSpotify && (
            <Notice>
              Spotify links need a one-time setup.{' '}
              <button onClick={onSetup} className="underline">Open Setup</button>
            </Notice>
          )}

          <ScanFolders
            enabled={scanEnabled}
            onEnabledChange={setScanEnabled}
            selection={selectedFolders}
            onSelectionChange={setSelectedFolders}
          />

          <ErrorBox>{error}</ErrorBox>

          <Button onClick={analyze} disabled={!validLinks.length || needsSpotify} className="self-end">
            Continue
          </Button>
        </div>
      )}

      {step === 'analyzing' && (
        <div className="flex flex-col gap-5">
          <ProgressCard
            label={status?.phase === 'matching' ? `Matching "${status.playlist}"` : 'Reading playlists...'}
            processed={status?.processed ?? 0}
            total={status?.total ?? 0}
            current={status?.current}
            color="#30d158"
          />
          {status?.sources?.length > 1 && (
            <Card className="px-5 py-3 text-xs text-zinc-500">
              {status.sources.map((s) => (
                <p key={s.url} className="truncate">
                  {s.name || s.url}
                  {s.total ? ` · ${s.total} tracks` : ''}
                  {s.error && <span className="text-[#ff6961]"> · {s.error}</span>}
                </p>
              ))}
            </Card>
          )}
        </div>
      )}

      {step === 'select' && status && (
        <div className="flex flex-col gap-5">
          <SelectionHeader
            title={status.playlist}
            subtitle={`${checked.size} of ${status.matched.length} tracks selected${
              duplicates.length ? ` · ${duplicates.length} already in your library` : ''
            }${status.unmatched.length ? ` · ${status.unmatched.length} not found` : ''}`}
            onSelectAll={() => checked.replace(fresh.map((v) => v.id))}
            onClear={checked.clear}
          />

          {fresh.length > 0 ? (
            <TrackList tracks={fresh} checked={checked.selected} onToggle={checked.toggle} maxHeight={duplicates.length ? '300px' : '420px'} />
          ) : (
            <Notice tone="info">Every track is already in your library.</Notice>
          )}

          {duplicates.length > 0 && (
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <button onClick={() => setShowDuplicates((v) => !v)} className="text-[13px] font-medium text-[#ff9f0a] hover:underline">
                  {showDuplicates ? 'Hide' : 'Show'} {duplicates.length} already in your library
                </button>
                {showDuplicates && (
                  <div className="flex gap-2 text-xs">
                    <button onClick={() => checked.replace([...checked.selected, ...duplicates.map((v) => v.id)])} className="text-[#0a84ff] hover:underline">
                      Download again
                    </button>
                    <span className="text-zinc-700">·</span>
                    <button onClick={() => checked.replace([...checked.selected].filter((id) => !duplicateIds.has(id)))} className="text-[#0a84ff] hover:underline">
                      Skip all
                    </button>
                  </div>
                )}
              </div>
              {showDuplicates && (
                <TrackList tracks={duplicates} checked={checked.selected} onToggle={checked.toggle} maxHeight="220px" />
              )}
            </div>
          )}

          {status.unmatched.length > 0 && (
            <Card className="max-h-[180px] overflow-y-auto">
              <div className="border-b border-white/[0.06] px-5 py-3 text-[13px] font-medium text-[#ff9f0a]">
                Not found on any provider
              </div>
              {status.unmatched.map((track, index) => (
                <p key={index} className="truncate border-t border-white/[0.05] px-5 py-2.5 text-sm text-zinc-500 first:border-t-0">
                  {track.artists.length ? `${track.artists.join(', ')} - ` : ''}
                  {track.title}
                </p>
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
          playlistName={status.sources.length === 1 ? status.playlist : 'Mixed links'}
          operation={operation}
          onReset={reset}
        />
      )}
    </div>
  )
}
