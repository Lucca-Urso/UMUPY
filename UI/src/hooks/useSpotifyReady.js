import { useEffect, useState } from 'react'
import { call } from '../api'

export function useSpotifyReady() {
  const [ready, setReady] = useState(null)
  const refresh = () => call('spotify_ready').then(setReady)

  useEffect(() => {
    refresh()
  }, [])

  return [ready, refresh]
}
