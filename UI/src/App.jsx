import { useState } from 'react'
import Home from './views/Home'
import Download from './views/Download'
import Spotify from './views/Spotify'
import Rekordbox from './views/Rekordbox'
import History from './views/History'

export default function App() {
  const [view, setView] = useState('home')
  const goHome = () => setView('home')

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {view === 'home' && <Home onNavigate={setView} />}
      {view === 'download' && <Download onBack={goHome} />}
      {view === 'spotify' && <Spotify onBack={goHome} />}
      {view === 'rekordbox' && <Rekordbox onBack={goHome} />}
      {view === 'history' && <History onBack={goHome} />}
    </div>
  )
}
