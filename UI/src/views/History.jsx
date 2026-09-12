import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, Spinner, StatusIcon } from '../components/ui'

const OPERATION_LABELS = {
  youtube_download: 'YouTube Download',
  spotify_download: 'Spotify Download',
  spotify_convert: 'Spotify Conversion',
  rekordbox_create: 'RekordBox Playlists',
  sync_check: 'Sync Check',
  sync_delete: 'Sync Delete',
  sync_download: 'Sync Download',
}

const STATUS_STYLES = {
  completed: 'bg-[#30d158]/15 text-[#30d158]',
  completed_with_errors: 'bg-[#ff9f0a]/15 text-[#ff9f0a]',
  failed: 'bg-[#ff453a]/15 text-[#ff6961]',
  running: 'bg-[#0a84ff]/15 text-[#0a84ff]',
}

const STATUS_LABELS = {
  completed: 'Completed',
  completed_with_errors: 'With errors',
  failed: 'Failed',
  running: 'Running',
}

function ItemDot({ status }) {
  if (status === 'ok') return <StatusIcon ok />
  if (status === 'failed') return <StatusIcon ok={false} />
  return (
    <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center">
      <span className="h-2 w-2 rounded-full bg-[#ff9f0a]" />
    </span>
  )
}

export default function History({ onBack }) {
  const [runs, setRuns] = useState(null)
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)

  useEffect(() => {
    call('history_list').then(setRuns)
  }, [])

  const openRun = async (run) => {
    setSelected(run)
    setDetail(null)
    setDetail(await call('history_get', run.id))
  }

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
      <header className="flex items-center gap-3 pt-8 pb-10">
        <button
          onClick={() => (selected ? (setSelected(null), setDetail(null)) : onBack())}
          className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.06] text-zinc-400 transition-colors hover:bg-white/[0.12] hover:text-white"
        >
          <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 6l-6 6 6 6" />
          </svg>
        </button>
        <div>
          <h1 className="text-xl font-semibold text-white">History</h1>
          <p className="text-[13px] text-zinc-500">
            {selected ? OPERATION_LABELS[selected.operation] || selected.operation : 'Past operations and logs'}
          </p>
        </div>
      </header>

      {!selected && !runs && (
        <div className="flex flex-1 items-center justify-center pb-24">
          <Spinner className="h-8 w-8" />
        </div>
      )}

      {!selected && runs && runs.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 pb-24 text-center">
          <p className="text-sm text-zinc-400">No operations yet</p>
          <p className="text-xs text-zinc-600">Downloads, conversions and playlist imports will show up here.</p>
        </div>
      )}

      {!selected && runs && runs.length > 0 && (
        <Card className="overflow-hidden">
          {runs.map((run, index) => (
            <div
              key={run.id}
              onClick={() => openRun(run)}
              className={`flex cursor-pointer items-center gap-4 px-5 py-4 transition-colors hover:bg-white/[0.04] ${
                index > 0 ? 'border-t border-white/[0.05]' : ''
              }`}
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm text-zinc-100">{run.target || OPERATION_LABELS[run.operation] || run.operation}</p>
                <p className="mt-0.5 text-xs text-zinc-600">
                  {OPERATION_LABELS[run.operation] || run.operation} · {run.started_at}
                  {run.items > 0 && ` · ${run.succeeded ?? 0} ok${run.failed ? ` · ${run.failed} failed` : ''} · ${run.items} items`}
                </p>
              </div>
              <span className={`rounded-full px-2.5 py-0.5 text-[11px] font-medium ${STATUS_STYLES[run.status] || STATUS_STYLES.running}`}>
                {STATUS_LABELS[run.status] || run.status}
              </span>
              <svg viewBox="0 0 24 24" className="h-4 w-4 shrink-0 fill-none stroke-zinc-600" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 6l6 6-6 6" />
              </svg>
            </div>
          ))}
        </Card>
      )}

      {selected && (
        <div className="flex flex-col gap-5">
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-white">
              {selected.target || OPERATION_LABELS[selected.operation] || selected.operation}
            </h2>
            <p className="mt-1 text-[13px] text-zinc-500">
              Started {selected.started_at}
              {selected.finished_at && ` · finished ${selected.finished_at}`}
            </p>
            <span className={`mt-3 inline-block rounded-full px-2.5 py-0.5 text-[11px] font-medium ${STATUS_STYLES[selected.status] || ''}`}>
              {STATUS_LABELS[selected.status] || selected.status}
            </span>
          </Card>

          {!detail && (
            <div className="flex items-center justify-center py-12">
              <Spinner className="h-6 w-6" />
            </div>
          )}

          {detail && detail.items.length > 0 && (
            <Card className="max-h-[440px] overflow-y-auto">
              {detail.items.map((item, index) => (
                <div
                  key={item.id}
                  className={`flex items-start gap-4 px-5 py-3 ${index > 0 ? 'border-t border-white/[0.05]' : ''}`}
                >
                  <ItemDot status={item.status} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm text-zinc-300">{item.title}</p>
                    {item.detail && <p className="truncate text-xs text-zinc-600">{item.detail}</p>}
                    {item.error && <p className="mt-0.5 text-xs break-words text-[#ff6961]">{item.error}</p>}
                  </div>
                  {['not_found', 'retrying', 'blocked', 'paused', 'skipped', 'missing', 'orphan'].includes(item.status) && (
                    <span className="rounded-full bg-[#ff9f0a]/15 px-2.5 py-0.5 text-[11px] font-medium text-[#ff9f0a]">
                      {item.status.replace('_', ' ')}
                    </span>
                  )}
                </div>
              ))}
            </Card>
          )}

          {detail && detail.items.length === 0 && (
            <p className="py-8 text-center text-sm text-zinc-600">No items recorded for this run.</p>
          )}
        </div>
      )}
    </div>
  )
}
