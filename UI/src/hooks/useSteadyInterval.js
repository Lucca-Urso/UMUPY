import { useEffect, useRef } from 'react'

const workerSource = `
  let timer = null
  self.onmessage = (event) => {
    clearInterval(timer)
    if (event.data > 0) timer = setInterval(() => self.postMessage('tick'), event.data)
  }
`

export function useSteadyInterval(callback, interval, active = true) {
  const saved = useRef(callback)
  saved.current = callback

  useEffect(() => {
    if (!active) return undefined
    let cancelled = false
    let busy = false

    const tick = async () => {
      if (busy || cancelled) return
      busy = true
      try {
        await saved.current()
      } finally {
        busy = false
      }
    }

    let worker = null
    let fallback = null

    try {
      worker = new Worker(URL.createObjectURL(new Blob([workerSource], { type: 'application/javascript' })))
      worker.onmessage = tick
      worker.postMessage(interval)
    } catch {
      fallback = setInterval(tick, interval)
    }

    const onVisible = () => {
      if (!document.hidden) tick()
    }
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener('focus', onVisible)
    tick()

    return () => {
      cancelled = true
      if (worker) worker.terminate()
      if (fallback) clearInterval(fallback)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener('focus', onVisible)
    }
  }, [interval, active])
}
