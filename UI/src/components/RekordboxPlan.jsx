import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, Checkbox, ErrorBox, Notice, StatusIcon } from './ui'

function Row({ item, checked, onToggle, note, tone = 'text-zinc-300' }) {
  return (
    <div
      onClick={onToggle}
      className="flex cursor-pointer items-center gap-4 border-t border-white/[0.05] px-5 py-3 transition-colors first:border-t-0 hover:bg-white/[0.04]"
    >
      <Checkbox checked={checked} onChange={onToggle} />
      <div className="min-w-0 flex-1">
        <p className={`truncate text-sm ${checked ? tone : 'text-zinc-500'}`}>
          {item.artist ? `${item.artist} - ` : ''}
          {item.title || item.path}
        </p>
        {note && <p className="truncate text-xs text-zinc-600">{note}</p>}
      </div>
    </div>
  )
}

export default function RekordboxPlan({ plan, onApplied, onBack, backLabel = 'Back' }) {
  const [addChecked, setAddChecked] = useState(new Set())
  const [removeChecked, setRemoveChecked] = useState(new Set())
  const [armed, setArmed] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    setAddChecked(new Set((plan?.add || []).map((t) => t.path)))
    setRemoveChecked(new Set())
    setResult(null)
    setError(null)
  }, [plan])

  if (!plan) return null

  if (plan.error) {
    return (
      <div className="flex flex-col gap-5">
        <ErrorBox>{plan.error}</ErrorBox>
        <Button variant="ghost" onClick={onBack} className="self-start">
          {backLabel}
        </Button>
      </div>
    )
  }

  const toggle = (setter) => (key) =>
    setter((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })

  const apply = async () => {
    if (!armed) {
      setArmed(true)
      return
    }
    setArmed(false)
    setBusy(true)
    setError(null)
    const outcome = await call('rekordbox_sync_apply', [...addChecked], [...removeChecked])
    setBusy(false)
    if (outcome.error) {
      setError(outcome.error)
      return
    }
    setResult(outcome)
    if (onApplied) onApplied(outcome)
  }

  const nothingSelected = !addChecked.size && !removeChecked.size
  const total = plan.add.length + plan.remove.length

  if (result) {
    return (
      <div className="flex flex-col items-center py-10 text-center">
        <StatusIcon ok={!result.errors.length} />
        <h2 className="mt-4 text-xl font-semibold text-white">
          "{plan.playlist}" updated in RekordBox
        </h2>
        <p className="mt-1 text-[13px] text-zinc-500">
          {result.added} added · {result.removed} removed
          {result.created ? ' · playlist created' : ''}
          {result.errors.length ? ` · ${result.errors.length} failed` : ''}
        </p>
        {result.backup && <p className="mt-2 text-xs text-zinc-600">Backup saved: {result.backup}</p>}
        <Button className="mt-6" onClick={onBack}>
          {backLabel}
        </Button>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-5">
      <div>
        <h2 className="text-lg font-semibold text-white">
          {plan.exists ? `Update "${plan.playlist}"` : `Create "${plan.playlist}"`}
        </h2>
        <p className="text-[13px] text-zinc-500">
          {plan.keep} already in the playlist · {plan.add.length} to add · {plan.remove.length} to remove
        </p>
        <p className="truncate text-xs text-zinc-600">{plan.folder}</p>
      </div>

      {plan.running && <Notice>RekordBox is open. Close it before applying the changes.</Notice>}

      {total === 0 && (
        <div className="flex flex-col items-center py-10 text-center">
          <StatusIcon ok />
          <h3 className="mt-4 text-lg font-semibold text-white">Playlist already in sync</h3>
        </div>
      )}

      {plan.add.length > 0 && (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
            <span className="text-[13px] font-medium text-zinc-200">Add to playlist</span>
            <span className="text-xs text-zinc-500">{addChecked.size} selected</span>
          </div>
          <div className="max-h-[260px] overflow-y-auto">
            {plan.add.map((item) => (
              <Row
                key={item.path}
                item={item}
                checked={addChecked.has(item.path)}
                onToggle={() => toggle(setAddChecked)(item.path)}
                note={item.in_collection ? null : 'New file · will also be added to your collection'}
              />
            ))}
          </div>
        </Card>
      )}

      {plan.remove.length > 0 && (
        <Card className="overflow-hidden">
          <div className="flex items-center justify-between border-b border-white/[0.06] px-5 py-3">
            <span className="text-[13px] font-medium text-zinc-200">Remove from playlist (file no longer in folder)</span>
            <span className="text-xs text-zinc-500">{removeChecked.size} selected</span>
          </div>
          <div className="max-h-[200px] overflow-y-auto">
            {plan.remove.map((item) => (
              <Row
                key={item.song_id}
                item={item}
                checked={removeChecked.has(item.song_id)}
                onToggle={() => toggle(setRemoveChecked)(item.song_id)}
                note="Only the playlist entry is removed. Your collection keeps the track."
                tone="text-[#ff6961]"
              />
            ))}
          </div>
        </Card>
      )}

      <ErrorBox>{error}</ErrorBox>

      <div className="flex items-center justify-between">
        <Button variant="ghost" onClick={onBack}>
          {backLabel}
        </Button>
        <div className="flex items-center gap-3">
          {armed && <span className="text-xs text-[#ff9f0a]">A backup of the database is saved first.</span>}
          <Button onClick={apply} disabled={nothingSelected || busy || plan.running}>
            {busy ? 'Applying...' : armed ? 'Confirm changes' : 'Apply to RekordBox'}
          </Button>
        </div>
      </div>
    </div>
  )
}
