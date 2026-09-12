export function Button({ children, onClick, variant = 'primary', disabled, className = '' }) {
  const styles = {
    primary: 'bg-[#0a84ff] text-white hover:bg-[#2b95ff] active:bg-[#0071e3] disabled:bg-white/10 disabled:text-zinc-500',
    secondary: 'bg-white/[0.08] text-zinc-100 hover:bg-white/[0.14] active:bg-white/[0.06]',
    ghost: 'bg-transparent text-zinc-400 hover:text-zinc-100 hover:bg-white/[0.06]',
    danger: 'bg-[#ff453a]/90 text-white hover:bg-[#ff453a]',
  }
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`rounded-full px-5 py-2.5 text-sm font-medium transition-colors duration-150 disabled:cursor-not-allowed ${styles[variant]} ${className}`}
    >
      {children}
    </button>
  )
}

export function Card({ children, className = '', style }) {
  return (
    <div className={`rounded-2xl border border-white/[0.08] bg-white/[0.04] ${className}`} style={style}>
      {children}
    </div>
  )
}

export function PageHeader({ title, subtitle, onBack, action }) {
  return (
    <header className="flex items-center gap-3 pt-8 pb-10">
      <button
        onClick={onBack}
        className="flex h-9 w-9 items-center justify-center rounded-full bg-white/[0.06] text-zinc-400 transition-colors hover:bg-white/[0.12] hover:text-white"
        aria-label="Back"
      >
        <svg viewBox="0 0 24 24" className="h-5 w-5 fill-none stroke-current" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M15 6l-6 6 6 6" />
        </svg>
      </button>
      <div className="min-w-0 flex-1">
        <h1 className="text-xl font-semibold text-white">{title}</h1>
        {subtitle && <p className="truncate text-[13px] text-zinc-500">{subtitle}</p>}
      </div>
      {action}
    </header>
  )
}

export function ErrorBox({ children }) {
  if (!children) return null
  return (
    <div className="rounded-xl border border-[#ff453a]/30 bg-[#ff453a]/10 px-4 py-3 text-sm text-[#ff6961]">{children}</div>
  )
}

export function Notice({ children, tone = 'warning' }) {
  const tones = {
    warning: 'border-[#ff9f0a]/30 bg-[#ff9f0a]/10 text-[#ff9f0a]',
    info: 'border-white/[0.08] bg-white/[0.04] text-zinc-400',
  }
  return <div className={`rounded-xl border px-4 py-3 text-sm ${tones[tone]}`}>{children}</div>
}

export function ProgressCard({ label, processed, total, current, color = '#0a84ff', children }) {
  const width = total ? `${Math.min(100, (processed / total) * 100)}%` : '10%'
  return (
    <Card className="p-6">
      <div className="mb-3 flex items-center justify-between text-sm">
        <span className="font-medium text-zinc-200">{label}</span>
        {total > 0 && (
          <span className="text-zinc-500">
            {processed} / {total}
          </span>
        )}
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]">
        <div className="h-full rounded-full transition-all duration-500" style={{ width, background: color }} />
      </div>
      {current && (
        <p className="mt-4 flex items-center gap-2.5 text-sm text-zinc-400">
          <Spinner className="h-4 w-4" />
          <span className="truncate">
            {current.retrying ? `Retrying on ${current.provider}: ` : ''}
            {current.track}
          </span>
        </p>
      )}
      {children}
    </Card>
  )
}

export function SelectionHeader({ title, subtitle, onSelectAll, onClear }) {
  return (
    <div className="flex items-end justify-between">
      <div className="min-w-0">
        <h2 className="truncate text-lg font-semibold text-white">{title}</h2>
        <p className="text-[13px] text-zinc-500">{subtitle}</p>
      </div>
      <div className="flex shrink-0 gap-2 text-[13px]">
        <button onClick={onSelectAll} className="text-[#0a84ff] hover:underline">
          Select all
        </button>
        <span className="text-zinc-700">·</span>
        <button onClick={onClear} className="text-[#0a84ff] hover:underline">
          Clear
        </button>
      </div>
    </div>
  )
}

export function Spinner({ className = '' }) {
  return (
    <div
      className={`h-5 w-5 animate-spin rounded-full border-2 border-white/20 border-t-[#0a84ff] ${className}`}
    />
  )
}

export function Toggle({ checked, onChange, label }) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-4">
      <span className="text-sm text-zinc-300">{label}</span>
      <span
        onClick={() => onChange(!checked)}
        className={`relative inline-flex h-7 w-12 shrink-0 items-center rounded-full transition-colors duration-200 ${
          checked ? 'bg-[#30d158]' : 'bg-white/[0.12]'
        }`}
      >
        <span
          className={`inline-block h-6 w-6 transform rounded-full bg-white shadow-md transition-transform duration-200 ${
            checked ? 'translate-x-[22px]' : 'translate-x-0.5'
          }`}
        />
      </span>
    </label>
  )
}

export function Checkbox({ checked, onChange }) {
  return (
    <span
      onClick={(e) => {
        e.stopPropagation()
        onChange(!checked)
      }}
      className={`flex h-[22px] w-[22px] shrink-0 cursor-pointer items-center justify-center rounded-md border transition-colors duration-150 ${
        checked ? 'border-[#0a84ff] bg-[#0a84ff]' : 'border-white/25 bg-transparent hover:border-white/50'
      }`}
    >
      {checked && (
        <svg viewBox="0 0 12 12" className="h-3 w-3 fill-none stroke-white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M2 6.5 4.5 9 10 3" />
        </svg>
      )}
    </span>
  )
}

export function StatusIcon({ ok }) {
  return ok ? (
    <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-[#30d158]/15">
      <svg viewBox="0 0 12 12" className="h-3 w-3 fill-none stroke-[#30d158]" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M2 6.5 4.5 9 10 3" />
      </svg>
    </span>
  ) : (
    <span className="flex h-[22px] w-[22px] shrink-0 items-center justify-center rounded-full bg-[#ff453a]/15">
      <svg viewBox="0 0 12 12" className="h-3 w-3 fill-none stroke-[#ff453a]" strokeWidth="2.2" strokeLinecap="round">
        <path d="M3 3l6 6M9 3l-6 6" />
      </svg>
    </span>
  )
}
