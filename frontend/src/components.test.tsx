// @vitest-environment jsdom
import React from 'react'
import { afterEach, expect, test, vi } from 'vitest'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import '@testing-library/jest-dom/vitest'
import { Badge, External, Select } from './components'

afterEach(cleanup)
test('evidence is escaped and unsafe links cannot execute', () => {
  render(<External href="javascript:alert(1)">Official offer</External>)
  expect(screen.queryByRole('link')).toBeNull()
  cleanup()
  render(<External href="https://example.com">{'<script>alert(1)</script>'}</External>)
  expect(document.querySelector('script')).toBeNull()
  expect(screen.getByRole('link')).toHaveAttribute('rel', 'noopener noreferrer')
  expect(screen.getByRole('link')).toHaveTextContent('<script>')
})
test('verification is communicated as text, not just color', () => {
  render(<Badge tone="amber">Partially verified</Badge>)
  expect(screen.getByText('Partially verified')).toBeVisible()
})
test('filter control has a label and returns the selected predicate', () => {
  const change = vi.fn()
  render(<Select label="Geographic eligibility" value="" options={['India eligible', 'Unclear']} onChange={change} />)
  fireEvent.change(screen.getByRole('combobox', { name: 'Geographic eligibility' }), { target: { value: 'Unclear' } })
  expect(change).toHaveBeenCalledWith('Unclear')
})
