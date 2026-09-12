import { useState } from 'react'
import Home from './views/Home'
import Downloader from './views/Downloader'
import PlaylistBuilder from './views/PlaylistBuilder'
import History from './views/History'
import Setup from './views/Setup'
import Synchronizer from './views/Synchronizer'

export default function App() {
  const [view, setView] = useState('home')
  const goHome = () => setView('home')

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {view === 'home' && <Home onNavigate={setView} />}
      {view === 'downloader' && <Downloader onBack={goHome} onSetup={() => setView('setup')} />}
      {view === 'synchronizer' && <Synchronizer onBack={goHome} onSetup={() => setView('setup')} />}
      {view === 'builder' && <PlaylistBuilder onBack={goHome} />}
      {view === 'history' && <History onBack={goHome} />}
      {view === 'setup' && <Setup onBack={goHome} />}
    </div>
  )
}
