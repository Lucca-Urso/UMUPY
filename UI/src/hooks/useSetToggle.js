import { useCallback, useState } from 'react'

export function useSetToggle(initial = []) {
  const [selected, setSelected] = useState(() => new Set(initial))

  const toggle = useCallback((key) => {
    setSelected((prev) => {
      const next = new Set(prev)
      next.has(key) ? next.delete(key) : next.add(key)
      return next
    })
  }, [])

  const replace = useCallback((keys) => setSelected(new Set(keys)), [])
  const clear = useCallback(() => setSelected(new Set()), [])

  return { selected, toggle, replace, clear, has: (key) => selected.has(key), size: selected.size }
}
