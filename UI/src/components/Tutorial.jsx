import { useState } from 'react'

export const TUTORIALS = {
  downloader: {
    title: 'Downloader',
    purpose: 'Turns playlists or single tracks from YouTube, Spotify or SoundCloud into MP3 files with artwork.',
    steps: [
      'Paste one or more links. The badge shows which service each link belongs to.',
      'Turn on "Scan Downloads for duplicates" to skip tracks you already have.',
      'Untick anything you do not want, then press Download.',
      'Tracks missing on one service are searched on the others automatically.',
    ],
  },
  synchronizer: {
    title: 'Synchronizer',
    purpose: 'Keeps a local folder or a RekordBox playlist equal to a playlist you follow online.',
    steps: [
      'Pick what should stay in sync: a folder on this computer or a RekordBox playlist.',
      'Pick where the music comes from: online links or a local folder.',
      'Review what is missing and what is extra. Nothing is downloaded, deleted or written without your confirmation.',
      'When the destination is RekordBox, files go to a Downloads folder first and only the playlist entries change.',
    ],
  },
  builder: {
    title: 'Playlist Builder',
    purpose: 'Creates RekordBox playlists from a playlist file or a folder of music you already imported into RekordBox.',
    steps: [
      'Choose an .xml or .txt playlist file, or a folder.',
      'Each track is matched against your RekordBox collection by title and artist.',
      'Untick playlists you do not want, then confirm. RekordBox must be closed.',
    ],
  },
  history: {
    title: 'History',
    purpose: 'Every download, sync and RekordBox change is recorded here.',
    steps: [
      'Open an entry to see each track, which service it came from and why something failed.',
      'Text can be selected and copied, useful when asking for help.',
    ],
  },
  setup: {
    title: 'Setup',
    purpose: 'One-time connections so UMUPY can read your playlists.',
    steps: [
      'Spotify: create a free app on the Spotify developer site and paste its two keys here.',
      'YouTube cookies: pick the browser where you are signed in. Use a secondary Google account if you can.',
      'FFmpeg converts audio. It ships with UMUPY; install it only if the check fails.',
    ],
  },
}

export function TutorialButton({ onClick, open }) {
  return (
    <button
      onClick={onClick}
      aria-label="How this works"
      className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
        open ? 'bg-[#0a84ff] text-white' : 'bg-white/[0.06] text-zinc-400 hover:bg-white/[0.12] hover:text-white'
      }`}
    >
      ?
    </button>
  )
}

export default function Tutorial({ id, open, onClose }) {
  const content = TUTORIALS[id]

  if (!open || !content) return null

  return (
    <div className="mb-6 rounded-2xl border border-[#0a84ff]/30 bg-[#0a84ff]/[0.06] p-5">
      <div className="flex items-start justify-between gap-4">
        <p className="text-sm text-zinc-200">{content.purpose}</p>
        <button onClick={onClose} className="shrink-0 text-xs text-[#0a84ff] hover:underline">
          Close
        </button>
      </div>
      <ol className="mt-3 flex flex-col gap-1.5 text-[13px] text-zinc-400">
        {content.steps.map((step, index) => (
          <li key={step} className="flex gap-2.5">
            <span className="shrink-0 text-[#0a84ff]">{index + 1}.</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
    </div>
  )
}

export function useTutorial() {
  const [open, setOpen] = useState(false)
  return { open, toggle: () => setOpen((v) => !v), close: () => setOpen(false) }
}
