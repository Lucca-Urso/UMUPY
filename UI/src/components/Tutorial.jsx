import { useState } from 'react'

const PRIVACY = {
  youtube: 'YouTube: public and unlisted playlists work. Private playlists and age-restricted videos need your YouTube login (Setup → cookies).',
  spotify: 'Spotify: your own playlists (public or private) and any public playlist. Spotify-made editorial playlists are blocked by Spotify for apps like this one.',
  soundcloud: 'SoundCloud: public sets work. For a private set, paste its "secret link" (the share link ending in /s-XXXX). Tracks marked Go+, preview-only or blocked in your country cannot be downloaded from SoundCloud; UMUPY looks for them on YouTube instead.',
}

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
    privacy: [PRIVACY.youtube, PRIVACY.spotify, PRIVACY.soundcloud],
  },
  synchronizer: {
    title: 'Synchronizer',
    purpose: 'Keeps a local folder or a RekordBox playlist equal to a playlist you follow online.',
    steps: [
      'Pick what should stay in sync: a folder on this computer or a RekordBox playlist.',
      'Pick where the music comes from: online links or a local folder.',
      'Review what is missing and what is extra. Nothing is downloaded, deleted or written without your confirmation.',
      'When the destination is RekordBox, files go to a Downloads folder first and only the playlist entries change. Your RekordBox collection is never touched.',
    ],
    privacy: [PRIVACY.youtube, PRIVACY.spotify, PRIVACY.soundcloud],
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
      'YouTube cookies: pick the browser where you are signed in, or paste them manually if the browser blocks it. Use a secondary Google account if you can.',
      'FFmpeg converts audio. It ships with UMUPY; install it only if the check fails.',
    ],
    privacy: [
      'Cookies and keys are saved only on this computer, in the Dependencies folder, and are never sent anywhere except to the service they belong to.',
    ],
  },
}

export function TutorialButton({ onClick, open }) {
  return (
    <button
      onClick={onClick}
      aria-label="Help"
      className={`flex h-9 shrink-0 items-center gap-2 rounded-full border px-4 text-sm font-medium transition-colors ${
        open
          ? 'border-[#0a84ff] bg-[#0a84ff] text-white'
          : 'border-[#0a84ff]/40 bg-[#0a84ff]/10 text-[#0a84ff] hover:bg-[#0a84ff]/20'
      }`}
    >
      <svg viewBox="0 0 24 24" className="h-4 w-4 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="9" />
        <path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 1-1 1.7M12 17h.01" />
      </svg>
      Help
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
      <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">How to use</p>
      <ol className="mt-1.5 flex flex-col gap-1.5 text-[13px] text-zinc-400">
        {content.steps.map((step, index) => (
          <li key={step} className="flex gap-2.5">
            <span className="shrink-0 text-[#0a84ff]">{index + 1}.</span>
            <span>{step}</span>
          </li>
        ))}
      </ol>
      {content.privacy && (
        <>
          <p className="mt-4 text-[11px] font-semibold uppercase tracking-wide text-zinc-500">Which playlists can be used</p>
          <ul className="mt-1.5 flex flex-col gap-1.5 text-[13px] text-zinc-400">
            {content.privacy.map((item) => (
              <li key={item} className="flex gap-2.5">
                <span className="shrink-0 text-[#0a84ff]">•</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}

export function useTutorial() {
  const [open, setOpen] = useState(false)
  return { open, toggle: () => setOpen((v) => !v), close: () => setOpen(false) }
}
