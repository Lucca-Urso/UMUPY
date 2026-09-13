import { useState } from 'react'
import { call } from '../api'
import { useSteadyInterval } from './useSteadyInterval'

export function usePolling(method, running, interval = 700) {
  const [status, setStatus] = useState(null)

  useSteadyInterval(
    async () => {
      const next = await call(method)
      setStatus(next)
    },
    interval,
    running,
  )

  return [status, setStatus]
}
