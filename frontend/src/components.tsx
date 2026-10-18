import type { ReactNode } from 'react'
import { safeHref } from './api'

export function Badge({ children, tone = '' }: { children: ReactNode, tone?: string }) {
  return <span className={'badge ' + tone}>{children}</span>
}

export function External({ href, children }: { href?: string, children: ReactNode }) {
  const url = safeHref(href)
  return url
    ? <a href={url} target="_blank" rel="noopener noreferrer">{children} ↗</a>
    : <span className="muted">Not stated</span>
}

export function Select({ label, value, options, onChange }: {
  label: string, value: string, options: string[], onChange: (value: string) => void
}) {
  return <label className="field">{label}
    <select aria-label={label} value={value} onChange={event => onChange(event.target.value)}>
      <option value="">All</option>
      {options.map(option => <option key={option}>{option}</option>)}
    </select>
  </label>
}
