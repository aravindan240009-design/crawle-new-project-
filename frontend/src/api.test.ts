import { describe, expect, test } from 'vitest'
import { safeHref, stamp } from './api'

describe('safe evidence links and dates', () => {
  test('rejects scripts and credential-like non-web links', () => {
    expect(safeHref('javascript:alert(1)')).toBeUndefined()
    expect(safeHref('file:///etc/passwd')).toBeUndefined()
    expect(safeHref('https://example.com/offer')).toBe('https://example.com/offer')
  })
  test('shows unknown timestamps honestly and uses IST', () => {
    expect(stamp(null)).toBe('Not yet')
    expect(stamp('2026-10-09T02:30:00Z')).toContain('08:00')
    expect(stamp('2026-10-09T02:30:00Z')).toContain('IST')
  })
})
