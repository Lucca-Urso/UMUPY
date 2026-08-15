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

export function Card({ children, className = '' }) {
  return (
    <div className={`rounded-2xl border border-white/[0.08] bg-white/[0.04] ${className}`}>
      {children}
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
