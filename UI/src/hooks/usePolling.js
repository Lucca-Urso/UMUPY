import { useEffect, useRef, useState } from 'react'
import { call } from '../api'

export function usePolling(method, running, interval = 700) {
  const [status, setStatus] = useState(null)
  const timer = useRef(null)

  useEffect(() => {
    if (!running) return undefined
    let cancelled = false
    const tick = async () => {
      const next = await call(method)
      if (!cancelled) setStatus(next)
    }
    tick()
    timer.current = setInterval(tick, interval)
    return () => {
      cancelled = true
      clearInterval(timer.current)
    }
  }, [method, running, interval])

  return [status, setStatus]
}
