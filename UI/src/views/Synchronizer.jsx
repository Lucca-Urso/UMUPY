import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, Checkbox, ErrorBox, Notice, PageHeader, ProgressCard, Spinner, StatusIcon } from '../components/ui'
import LinkList, { detectProvider } from '../components/LinkList'
import TrackList from '../components/TrackList'
import ScanFolders from '../components/ScanFolders'
import DownloadRunner from '../components/DownloadRunner'
import RekordboxPlan from '../components/RekordboxPlan'
import Tutorial, { TutorialButton, useTutorial } from '../components/Tutorial'
import { usePolling } from '../hooks/usePolling'
import { useSetToggle } from '../hooks/useSetToggle'
import { useSpotifyReady } from '../hooks/useSpotifyReady'

const DESTINATIONS = [
  { id: 'folder', title: 'Local folder', description: 'Download what is missing and spot files that left the playlist.' },
  { id: 'rekordbox', title: 'RekordBox playlist', description: 'Mirror a folder or an online playlist into RekordBox.' },
]

const SOURCES = [
  { id: 'providers', title: 'Online playlists', description: 'YouTube, Spotify or SoundCloud links. Files land in a local folder first.' },
  { id: 'folder', title: 'Local folder', description: 'Use the music you already have on disk.' },
]

function Choice({ options, value, onChange }) {
  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {options.map((option) => (
        <button
          key={option.id}
          onClick={() => onChange(option.id)}
          className={`rounded-2xl border p-5 text-left transition-colors ${
            value === option.id ? 'border-[#0a84ff] bg-[#0a84ff]/10' : 'border-white/[0.08] bg-white/[0.04] hover:bg-white/[0.07]'
          }`}
        >
          <p className="text-[15px] font-semibold text-zinc-100">{option.title}</p>
          <p className="mt-1 text-[13px] leading-relaxed text-zinc-500">{option.description}</p>
        </button>
      ))}
    </div>
  )
}

function FolderPicker({ folder, onPick, hint }) {
  return (
    <Card className="p-6">
      <h2 className="text-[13px] font-medium text-zinc-400">Local folder</h2>
      <div className="mt-3 flex items-center gap-3">
        <Button variant="secondary" onClick={onPick}>
          Choose folder
        </Button>
        <p className="min-w-0 flex-1 truncate text-xs text-zinc-400">{folder || hint}</p>
      </div>
    </Card>
  )
}

export default function Synchronizer({ onBack, onSetup }) {
  const [step, setStep] = useState('destination')
  const [destination, setDestination] = useState(null)
  const [source, setSource] = useState(null)
  const [links, setLinks] = useState([''])
  const [folder, setFolder] = useState(null)
  const [scanEnabled, setScanEnabled] = useState(false)
  const [selectedFolders, setSelectedFolders] = useState(new Set(['__all__']))
  const [spotify] = useSpotifyReady()
  const [error, setError] = useState(null)
  const orphans = useSetToggle()
  const missing = useSetToggle()
  const [deleteArmed, setDeleteArmed] = useState(false)
  const [deleteResults, setDeleteResults] = useState(null)
  const [plan, setPlan] = useState(null)
  const [sync, setSync] = usePolling('get_sync_status', step === 'analyzing')
  const [chain] = usePolling('get_chain_status', step === 'planning')
  const tutorial = useTutorial()

  const validLinks = links.map((l) => l.trim()).filter((l) => l && detectProvider(l))
  const needsSpotify = validLinks.some((l) => detectProvider(l) === 'spotify') && spotify && !spotify.ready
  const toRekordbox = destination === 'rekordbox'
  const fromProviders = !toRekordbox || source === 'providers'

  useEffect(() => {
    if (step !== 'analyzing' || !sync || sync.running) return
    if (sync.error) {
      setError(sync.error)
      setStep('setup')
      return
    }
    orphans.clear()
    missing.replace(sync.missing.filter((m) => m.video && !m.video.duplicate).map((m) => m.spotify_id || m.id))
    setStep('results')
  }, [sync, step])

  useEffect(() => {
    if (step !== 'planning' || !chain || chain.running) return
    if (chain.error) {
      setError(chain.error)
      setStep('results')
      return
    }
    setPlan(chain.rekordbox)
    setStep('rekordbox')
  }, [chain, step])

  const pickFolder = async () => {
    const path = await call('select_folder')
    if (path) setFolder(path)
  }

  const analyze = async () => {
    setError(null)
    setDeleteResults(null)
    setDeleteArmed(false)
    setPlan(null)
    if (fromProviders) {
      setStep('analyzing')
      setSync(null)
      const scan = !toRekordbox && scanEnabled ? [...selectedFolders] : null
      await call('start_chain', validLinks, folder, scan)
    } else {
      setStep('loading')
      const result = await call('rekordbox_sync_plan', folder, null)
      setPlan(result)
      setStep('rekordbox')
    }
  }

  const deleteOrphans = async () => {
    if (!deleteArmed) {
      setDeleteArmed(true)
      return
    }
    setDeleteArmed(false)
    const paths = sync.orphans.filter((o) => orphans.has(o.path)).map((o) => o.path)
    const results = await call('sync_delete', paths)
    setDeleteResults(results)
    setSync((prev) => ({ ...prev, orphans: prev.orphans.filter((o) => !results.some((r) => r.ok && r.path === o.path)) }))
    orphans.clear()
  }

  const continueToRekordbox = async () => {
    setStep('planning')
    await call('start_chain_download', [], true)
  }

  const reset = () => {
    setStep('destination')
    setDestination(null)
    setSource(null)
    setLinks([''])
    setFolder(null)
    setError(null)
    setPlan(null)
    setSync(null)
    setDeleteResults(null)
  }

  const missingKey = (m) => m.spotify_id || m.id
  const missingWithVideo = sync?.missing.filter((m) => m.video) ?? []
  const missingNotFound = sync?.missing.filter((m) => !m.video) ?? []
  const selectedVideos = missingWithVideo.filter((m) => missing.has(missingKey(m))).map((m) => m.video)

  const subtitle = toRekordbox
    ? `To RekordBox${source ? ` · from ${source === 'providers' ? 'online playlists' : 'a local folder'}` : ''}`
    : destination
      ? 'To a local folder · from online playlists'
      : 'Online playlists → local folder → RekordBox'

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
      <PageHeader
        title="Synchronizer"
        subtitle={subtitle}
        onBack={step === 'destination' ? onBack : reset}
        action={<TutorialButton onClick={tutorial.toggle} open={tutorial.open} />}
      />
      <Tutorial id="synchronizer" open={tutorial.open} onClose={tutorial.close} />

      {step === 'destination' && (
        <div className="flex flex-col gap-5">
          <p className="text-sm text-zinc-400">What do you want to keep in sync?</p>
          <Choice options={DESTINATIONS} value={destination} onChange={setDestination} />
          <Button
            className="self-end"
            disabled={!destination}
            onClick={() => {
              if (destination === 'folder') setSource('providers')
              setStep(destination === 'rekordbox' ? 'source' : 'setup')
            }}
          >
            Continue
          </Button>
        </div>
      )}

      {step === 'source' && (
        <div className="flex flex-col gap-5">
          <p className="text-sm text-zinc-400">Where does the music come from?</p>
          <Choice options={SOURCES} value={source} onChange={setSource} />
          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => setStep('destination')}>
              Back
            </Button>
            <Button disabled={!source} onClick={() => setStep('setup')}>
              Continue
            </Button>
          </div>
        </div>
      )}

      {step === 'setup' && (
        <div className="flex flex-col gap-5">
          {fromProviders && <LinkList links={links} onChange={setLinks} placeholder="https://open.spotify.com/playlist/..." />}
          {needsSpotify && (
            <Notice>
              Spotify links need a one-time setup.{' '}
              <button onClick={onSetup} className="underline">Open Setup</button>
            </Notice>
          )}

          <FolderPicker
            folder={folder}
            onPick={pickFolder}
            hint={fromProviders ? 'Optional · defaults to Downloads/<playlist name>' : 'Required'}
          />

          {fromProviders && !toRekordbox && (
            <ScanFolders
              enabled={scanEnabled}
              onEnabledChange={setScanEnabled}
              selection={selectedFolders}
              onSelectionChange={setSelectedFolders}
            />
          )}

          <ErrorBox>{error}</ErrorBox>

          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={() => setStep(toRekordbox ? 'source' : 'destination')}>
              Back
            </Button>
            <Button onClick={analyze} disabled={fromProviders ? !validLinks.length || needsSpotify : !folder}>
              Compare
            </Button>
          </div>
        </div>
      )}

      {step === 'loading' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 pb-24">
          <Spinner className="h-8 w-8" />
          <p className="text-sm text-zinc-400">Comparing with your RekordBox collection...</p>
        </div>
      )}

      {step === 'analyzing' && (
        <ProgressCard
          label={
            !sync?.phase || sync.phase === 'fetching'
              ? 'Reading playlists...'
              : sync.phase === 'comparing'
                ? 'Comparing with the local folder...'
                : 'Finding download sources for missing tracks'
          }
          processed={sync?.processed ?? 0}
          total={sync?.phase === 'matching' ? sync.total : 0}
          current={sync?.current}
          color="#30d158"
        />
      )}

      {step === 'results' && sync && (
        <div className="flex flex-col gap-5">
          <div>
            <h2 className="truncate text-lg font-semibold text-white">{sync.playlist}</h2>
            <p className="text-[13px] text-zinc-500">
              {sync.in_sync} in sync · {sync.missing.length} missing locally · {sync.orphans.length} local files not in the playlist
            </p>
            <p className="truncate text-xs text-zinc-600">{sync.folder}</p>
          </div>

          <ErrorBox>{error}</ErrorBox>

          {sync.orphans.length === 0 && sync.missing.length === 0 && (
            <div className="flex flex-col items-center py-8 text-center">
              <StatusIcon ok />
              <h3 className="mt-4 text-lg font-semibold text-white">Folder in sync</h3>
            </div>
          )}

          {sync.orphans.length > 0 && (
            <Card className="overflow-hidden">
              <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
                <span className="text-[13px] font-medium text-zinc-200">Local files not in the playlist</span>
                <span className="text-xs text-zinc-500">{orphans.size} selected</span>
              </div>
              <div className="max-h-[220px] overflow-y-auto">
                {sync.orphans.map((orphan) => {
                  const toggle = () => orphans.toggle(orphan.path)
                  return (
                    <div
                      key={orphan.path}
                      onClick={toggle}
                      className="flex cursor-pointer items-center gap-4 border-t border-white/[0.05] px-5 py-3 transition-colors first:border-t-0 hover:bg-white/[0.04]"
                    >
                      <Checkbox checked={orphans.has(orphan.path)} onChange={toggle} />
                      <span className="flex-1 truncate text-sm text-zinc-300">{orphan.filename}</span>
                    </div>
                  )
                })}
              </div>
              <div className="flex items-center justify-end gap-3 border-t border-white/[0.06] px-5 py-3">
                {deleteArmed && <span className="text-xs text-[#ff6961]">This permanently deletes the files from {sync.folder}.</span>}
                <Button variant="danger" onClick={deleteOrphans} disabled={!orphans.size}>
                  {deleteArmed ? `Confirm delete ${orphans.size}` : `Delete ${orphans.size || ''} selected`}
                </Button>
              </div>
            </Card>
          )}

          {deleteResults && (
            <Notice tone="info">
              {deleteResults.filter((r) => r.ok).length} file(s) deleted
              {deleteResults.some((r) => !r.ok) && <span className="text-[#ff6961]"> · {deleteResults.filter((r) => !r.ok).length} failed</span>}
            </Notice>
          )}

          {sync.missing.length > 0 && (
            <div className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-zinc-200">Missing locally</span>
                <span className="text-xs text-zinc-500">{missing.size} selected to download</span>
              </div>
              {missingWithVideo.length > 0 && (
                <TrackList
                  tracks={missingWithVideo.map((m) => ({ ...m.video, id: missingKey(m), origin: { title: m.title, artists: m.artists } }))}
                  checked={missing.selected}
                  onToggle={missing.toggle}
                  maxHeight="260px"
                />
              )}
              {missingNotFound.length > 0 && (
                <Card className="max-h-[160px] overflow-y-auto">
                  <div className="border-b border-white/[0.06] px-5 py-3 text-[13px] font-medium text-[#ff9f0a]">Not found on any provider</div>
                  {missingNotFound.map((m) => (
                    <p key={missingKey(m)} className="truncate border-t border-white/[0.05] px-5 py-2.5 text-sm text-zinc-500 first:border-t-0">
                      {m.artists.length ? `${m.artists.join(', ')} - ` : ''}
                      {m.title}
                    </p>
                  ))}
                </Card>
              )}
            </div>
          )}

          <div className="flex items-center justify-between">
            <Button variant="ghost" onClick={reset}>
              New sync
            </Button>
            <div className="flex gap-3">
              {toRekordbox && (
                <Button variant="secondary" onClick={continueToRekordbox}>
                  {selectedVideos.length ? 'Skip downloads · go to RekordBox' : 'Continue to RekordBox'}
                </Button>
              )}
              {selectedVideos.length > 0 && (
                <Button onClick={() => setStep('downloading')}>
                  Download {selectedVideos.length} {selectedVideos.length === 1 ? 'track' : 'tracks'}
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {step === 'downloading' && sync && (
        <DownloadRunner
          videos={selectedVideos}
          playlistName={null}
          outputDirectory={sync.folder}
          operation="sync"
          starter={() => call('start_chain_download', selectedVideos, toRekordbox)}
          onReset={reset}
          resetLabel="New sync"
          doneActions={
            toRekordbox ? (
              <Button onClick={() => setStep('planning')}>Continue to RekordBox</Button>
            ) : (
              <Button onClick={reset}>New sync</Button>
            )
          }
        />
      )}

      {step === 'planning' && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 pb-24">
          <Spinner className="h-8 w-8" />
          <p className="text-sm text-zinc-400">Comparing the folder with your RekordBox collection...</p>
        </div>
      )}

      {step === 'rekordbox' && (
        <RekordboxPlan plan={plan} onBack={reset} backLabel="New sync" />
      )}
    </div>
  )
}
