import { useEffect, useState } from 'react'
import { call } from '../api'
import { Button, Card, Notice, PageHeader, Spinner, StatusIcon } from '../components/ui'
import Tutorial, { TutorialButton, useTutorial } from '../components/Tutorial'

function Section({ title, ok, children }) {
  return (
    <Card className="p-6">
      <div className="flex items-center gap-3">
        <StatusIcon ok={!!ok} />
        <h2 className="text-[15px] font-semibold text-zinc-100">{title}</h2>
      </div>
      <div className="mt-4">{children}</div>
    </Card>
  )
}

function Field({ label, value, onChange, type = 'text' }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-zinc-400">{label}</span>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoComplete="off"
        spellCheck={false}
        className="w-full rounded-xl border border-white/[0.1] bg-black/40 px-4 py-3 text-sm text-zinc-100 outline-none transition-colors focus:border-[#0a84ff]"
      />
    </label>
  )
}

export default function Setup({ onBack }) {
  const [status, setStatus] = useState(null)
  const [clientId, setClientId] = useState('')
  const [clientSecret, setClientSecret] = useState('')
  const [spotifyMessage, setSpotifyMessage] = useState(null)
  const [busy, setBusy] = useState(null)
  const [browser, setBrowser] = useState('')
  const [cookieMessage, setCookieMessage] = useState(null)
  const tutorial = useTutorial()

  const refresh = () => call('setup_status').then((s) => {
    setStatus(s)
    setBrowser(s.cookies.browser || '')
  })

  useEffect(() => {
    refresh()
  }, [])

  const saveSpotify = async () => {
    setBusy('spotify')
    setSpotifyMessage(null)
    const saved = await call('save_spotify_credentials', clientId, clientSecret)
    if (saved.error) {
      setSpotifyMessage({ ok: false, text: saved.error })
      setBusy(null)
      return
    }
    const test = await call('test_spotify_credentials')
    setSpotifyMessage(test.ok ? { ok: true, text: 'Connected to Spotify.' } : { ok: false, text: test.error })
    setClientId('')
    setClientSecret('')
    setBusy(null)
    refresh()
  }

  const testCookies = async () => {
    setBusy('cookies')
    setCookieMessage(null)
    const result = await call('test_cookies', browser)
    if (result.ok) {
      await call('set_cookies_browser', browser)
      setCookieMessage({ ok: true, text: result.detail })
    } else {
      setCookieMessage({ ok: false, text: result.error })
    }
    setBusy(null)
    refresh()
  }

  const clearCookies = async () => {
    await call('set_cookies_browser', '')
    setBrowser('')
    setCookieMessage(null)
    refresh()
  }

  if (!status) {
    return (
      <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
        <PageHeader title="Setup" onBack={onBack} />
        <div className="flex flex-1 items-center justify-center pb-24">
          <Spinner className="h-8 w-8" />
        </div>
      </div>
    )
  }

  const selected = status.cookies.browsers.find((b) => b.id === browser)

  return (
    <div className="mx-auto flex min-h-screen max-w-2xl flex-col px-8 pb-12">
      <PageHeader
        title="Setup"
        subtitle="One-time connections. Everything stays on this computer."
        onBack={onBack}
        action={<TutorialButton onClick={tutorial.toggle} open={tutorial.open} />}
      />
      <Tutorial id="setup" open={tutorial.open} onClose={tutorial.close} />

      <div className="flex flex-col gap-5">
        <Section title="Spotify" ok={status.spotify.ready}>
          <p className="text-[13px] leading-relaxed text-zinc-500">
            Needed only for Spotify links. Create a free app at{' '}
            <span className="text-zinc-300">developer.spotify.com/dashboard</span> with redirect URI{' '}
            <code className="rounded bg-black/40 px-1.5 py-0.5 text-xs text-zinc-300">http://127.0.0.1:8888/callback</code>, then paste its keys here.
          </p>
          <div className="mt-4 flex flex-col gap-3">
            <Field label="Client ID" value={clientId} onChange={setClientId} />
            <Field label="Client Secret" value={clientSecret} onChange={setClientSecret} type="password" />
          </div>
          {spotifyMessage && (
            <p className={`mt-3 text-sm ${spotifyMessage.ok ? 'text-[#30d158]' : 'text-[#ff6961]'}`}>{spotifyMessage.text}</p>
          )}
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-zinc-600">{status.spotify.ready ? 'Keys saved. Pasting new keys replaces them.' : 'Not connected yet.'}</span>
            <Button onClick={saveSpotify} disabled={!clientId.trim() || !clientSecret.trim() || busy === 'spotify'}>
              {busy === 'spotify' ? 'Connecting...' : 'Save and connect'}
            </Button>
          </div>
        </Section>

        <Section title="YouTube cookies" ok={!!status.cookies.browser || !!status.cookies.file}>
          <p className="text-[13px] leading-relaxed text-zinc-500">
            Optional. Lets UMUPY use your YouTube login for age-restricted tracks and fewer blocks. Pick the browser where you are signed in to YouTube.
            Prefer a secondary Google account.
          </p>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {status.cookies.browsers.map((b) => (
              <button
                key={b.id}
                onClick={() => setBrowser(b.id)}
                className={`rounded-xl border px-3 py-2.5 text-left text-sm transition-colors ${
                  browser === b.id ? 'border-[#0a84ff] bg-[#0a84ff]/10 text-zinc-100' : 'border-white/[0.08] bg-white/[0.03] text-zinc-300 hover:bg-white/[0.06]'
                }`}
              >
                {b.label}
                {b.recommended && <span className="ml-1.5 text-[11px] text-[#30d158]">recommended</span>}
              </button>
            ))}
          </div>
          {selected?.note && <Notice>{selected.note}</Notice>}
          {cookieMessage && (
            <p className={`mt-3 text-sm ${cookieMessage.ok ? 'text-[#30d158]' : 'text-[#ff6961]'}`}>{cookieMessage.text}</p>
          )}
          <div className="mt-4 flex items-center justify-between">
            <span className="text-xs text-zinc-600">
              {status.cookies.browser
                ? `Using cookies from ${status.cookies.browser}.`
                : status.cookies.file
                  ? 'Using a cookies.txt file from the Dependencies folder.'
                  : 'Not using a YouTube login.'}
            </span>
            <div className="flex gap-2">
              {status.cookies.browser && (
                <Button variant="ghost" onClick={clearCookies}>
                  Stop using
                </Button>
              )}
              <Button onClick={testCookies} disabled={!browser || busy === 'cookies'}>
                {busy === 'cookies' ? 'Checking...' : 'Test and use'}
              </Button>
            </div>
          </div>
        </Section>

        <Section title="Audio tools" ok={status.ffmpeg.ok && status.deno.ok}>
          <div className="flex flex-col gap-2 text-[13px]">
            <p className={status.ffmpeg.ok ? 'text-zinc-400' : 'text-[#ff6961]'}>
              FFmpeg {status.ffmpeg.ok ? '· found' : '· missing. Install it from ffmpeg.org or drop the binary in the Dependencies folder.'}
            </p>
            <p className={status.deno.ok ? 'text-zinc-400' : 'text-[#ff6961]'}>
              Deno {status.deno.ok ? '· found' : '· missing. Install it from deno.com; YouTube downloads fail without it.'}
            </p>
          </div>
          <div className="mt-4 flex items-center justify-between">
            <span className="truncate text-xs text-zinc-600">Data folder: {status.data_directory}</span>
            <Button variant="secondary" onClick={() => call('open_data_directory')}>
              Open folder
            </Button>
          </div>
        </Section>
      </div>
    </div>
  )
}
