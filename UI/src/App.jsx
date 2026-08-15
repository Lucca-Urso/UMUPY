import { useState } from 'react'
import Home from './views/Home'
import Download from './views/Download'

export default function App() {
  const [view, setView] = useState('home')

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {view === 'home' && <Home onNavigate={setView} />}
      {view === 'download' && <Download onBack={() => setView('home')} />}
    </div>
  )
}
