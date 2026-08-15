import { useEffect, useState } from 'react'
import { call } from '../api'
import { Card, Toggle, Checkbox } from './ui'

export default function ScanFolders({ enabled, onEnabledChange, selection, onSelectionChange }) {
  const [folders, setFolders] = useState([])

  useEffect(() => {
    if (enabled) call('list_download_folders').then(setFolders)
  }, [enabled])

  const toggle = (name) => {
    const next = new Set(selection)
    if (name === '__all__') {
      onSelectionChange(new Set(['__all__']))
      return
    }
    next.delete('__all__')
    next.has(name) ? next.delete(name) : next.add(name)
    onSelectionChange(next.size ? next : new Set(['__all__']))
  }

  return (
    <Card className="p-6">
      <Toggle checked={enabled} onChange={onEnabledChange} label="Scan Downloads for duplicates" />
      {enabled && (
        <div className="mt-5 flex flex-col gap-1 border-t border-white/[0.06] pt-4">
          <Row name="All folders" checked={selection.has('__all__')} onToggle={() => toggle('__all__')} />
          {folders.map((name) => (
            <Row key={name} name={name} checked={selection.has(name)} onToggle={() => toggle(name)} />
          ))}
        </div>
      )}
    </Card>
  )
}

function Row({ name, checked, onToggle }) {
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
