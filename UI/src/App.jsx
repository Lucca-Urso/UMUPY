import { useState } from 'react'
import Home from './views/Home'
import Download from './views/Download'
import Rekordbox from './views/Rekordbox'
import History from './views/History'
import Sync from './views/Sync'

export default function App() {
  const [view, setView] = useState('home')
  const goHome = () => setView('home')

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {view === 'home' && <Home onNavigate={setView} />}
      {view === 'downloader' && <Download onBack={goHome} />}
      {view === 'synchronizer' && <Sync onBack={goHome} />}
      {view === 'builder' && <Rekordbox onBack={goHome} />}
      {view === 'history' && <History onBack={goHome} />}
    </div>
  )
}
