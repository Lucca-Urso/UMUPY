import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, StatusIcon } from './ui'
import { useSteadyInterval } from '../hooks/useSteadyInterval'

export default function DownloadRunner({
  videos,
  playlistName,
  onReset,
  resetLabel = 'New download',
  operation = 'youtube',
  outputDirectory = null,
  starter = null,
  onDone = null,
  doneActions = null,
}) {
  const [status, setStatus] = useState(null)
  const [outputDir, setOutputDir] = useState(null)
  const [started, setStarted] = useState(false)
  const [done, setDone] = useState(false)

  useEffect(() => {
    let cancelled = false
    ;(async () => {
      const dir = starter ? await starter() : await call('start_download', videos, playlistName, operation, outputDirectory)
      if (cancelled) return
      setOutputDir(typeof dir === 'string' ? dir : dir?.error || null)
      setStarted(true)
    })()
    return () => {
      cancelled = true
    }
  }, [])

  useSteadyInterval(
    async () => {
      const s = await call('get_status')
      setStatus(s)
      if (!s.running && s.items.length >= videos.length) {
        setDone(true)
        if (onDone) onDone(s)
      }
    },
    800,
    started && !done,
  )

  if (done && status) {
    const failed = status.items.filter((i) => !i.ok)
    return (
      <div className="flex flex-col gap-5">
        <div className="flex flex-col items-center py-8 text-center">
          <StatusIcon ok={!failed.length} />
          <h2 className="mt-4 text-xl font-semibold text-white">
            {status.items.filter((i) => i.ok).length} of {status.total} tracks downloaded
          </h2>
          <p className="mt-1 text-[13px] text-zinc-500">{outputDir}</p>
        </div>

        {failed.length > 0 && (
          <Card className="max-h-[280px] overflow-y-auto">
            <div className="border-b border-white/[0.06] px-5 py-3 text-[13px] font-medium text-[#ff6961]">
              Failed downloads
            </div>
            {failed.map((item) => (
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
          {doneActions || <Button onClick={onReset}>{resetLabel}</Button>}
        </div>
      </div>
    )
  }

  return (
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
        {status?.paused && (
          <div className="mt-4 rounded-xl border border-[#ff9f0a]/30 bg-[#ff9f0a]/10 px-4 py-3 text-sm text-[#ff9f0a]">
            Paused to avoid a block. Resuming in {status.resume_in}s.
          </div>
        )}
        {status?.active?.length > 0 && (
          <div className="mt-4 flex flex-col gap-2">
            {status.active.map((item) => (
              <p key={item.id} className="flex items-center gap-2.5 text-sm text-zinc-400">
                <Spinner className="h-4 w-4" />
                <span className="truncate">
                  {item.retrying ? `Retrying on ${item.provider}: ` : ''}
                  {item.title}
                </span>
              </p>
            ))}
          </div>
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
  )
}
