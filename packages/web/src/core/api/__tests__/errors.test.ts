/**
 * Unit tests for extractApiError — structured API error helper.
 *
 * Plan: .claude/plans/BUNDLE_DEBUG_PHASE3_PLAN.md §3.1
 */
import { describe, it, expect } from '@jest/globals'
import { AxiosError, AxiosHeaders } from 'axios'
import { extractApiError } from '../errors'

function makeAxiosError(status: number, data: unknown, message = 'axios'): AxiosError {
  const err = new AxiosError(message)
  err.response = {
    status,
    data,
    statusText: 'Error',
    headers: {},
    config: { headers: new AxiosHeaders() } as never,
  }
  err.request = {}  // mark as an axios error that reached the server
  return err
}

function makeNetworkError(message = 'Network Error'): AxiosError {
  const err = new AxiosError(message)
  err.request = {}
  // Intentionally no response → network-level failure
  return err
}

describe('extractApiError', () => {
  // ─────────────────────────────────────────────────────────
  // Structured detail (bundle-workflow format)
  // ─────────────────────────────────────────────────────────

  it('returns structured code and localized message (es)', () => {
    const err = makeAxiosError(500, {
      detail: {
        code: 'BUNDLE_INTEGRITY_ERROR',
        message_es: 'Error de integridad',
        message_fr: "Erreur d'intégrité",
        message_en: 'Integrity error',
      },
    })
    const result = extractApiError(err, 'es')
    expect(result.code).toBe('BUNDLE_INTEGRITY_ERROR')
    expect(result.message).toBe('Error de integridad')
    expect(result.status).toBe(500)
    expect(result.isServerError).toBe(true)
    expect(result.isNetworkError).toBe(false)
    expect(result.isRetryable).toBe(true)  // 5xx is retryable
  })

  it('picks fr when locale=fr', () => {
    const err = makeAxiosError(409, {
      detail: {
        code: 'PAYMENT_ALREADY_IN_PROGRESS',
        message_es: 'Pago en curso',
        message_fr: 'Paiement en cours',
        message_en: 'Payment in progress',
      },
    })
    const result = extractApiError(err, 'fr')
    expect(result.code).toBe('PAYMENT_ALREADY_IN_PROGRESS')
    expect(result.message).toBe('Paiement en cours')
    expect(result.status).toBe(409)
    expect(result.isServerError).toBe(false)
    expect(result.isRetryable).toBe(false)  // 409 is NOT in retryable set
  })

  it('falls back to es when requested locale missing', () => {
    const err = makeAxiosError(422, {
      detail: {
        code: 'SOME_CODE',
        message_es: 'Solo español',
      },
    })
    const result = extractApiError(err, 'en')
    expect(result.code).toBe('SOME_CODE')
    expect(result.message).toBe('Solo español')
  })

  // ─────────────────────────────────────────────────────────
  // Flat string detail (legacy FastAPI form)
  // ─────────────────────────────────────────────────────────

  it('handles flat string detail', () => {
    const err = makeAxiosError(404, { detail: 'Not found' })
    const result = extractApiError(err, 'es')
    expect(result.code).toBe('HTTP_404')
    expect(result.message).toBe('Not found')
    expect(result.status).toBe(404)
  })

  // ─────────────────────────────────────────────────────────
  // Pydantic validation array
  // ─────────────────────────────────────────────────────────

  it('handles pydantic validation array', () => {
    const err = makeAxiosError(422, {
      detail: [{ loc: ['body', 'email'], msg: 'field required', type: 'value_error' }],
    })
    const result = extractApiError(err, 'es')
    expect(result.code).toBe('VALIDATION_ERROR')
    expect(result.message).toBe('field required')
    expect(result.isRetryable).toBe(false)
  })

  // ─────────────────────────────────────────────────────────
  // Network / server / unknown
  // ─────────────────────────────────────────────────────────

  it('detects network error (no response)', () => {
    const err = makeNetworkError()
    const result = extractApiError(err, 'es')
    expect(result.code).toBe('NETWORK_ERROR')
    expect(result.isNetworkError).toBe(true)
    expect(result.isRetryable).toBe(true)
  })

  it('flags 503 as retryable server error', () => {
    const err = makeAxiosError(503, { detail: 'Service unavailable' })
    const result = extractApiError(err, 'es')
    expect(result.status).toBe(503)
    expect(result.isServerError).toBe(true)
    expect(result.isRetryable).toBe(true)
  })

  it('flags 429 as retryable non-server', () => {
    const err = makeAxiosError(429, { detail: 'Too many requests' })
    const result = extractApiError(err, 'es')
    expect(result.isServerError).toBe(false)
    expect(result.isRetryable).toBe(true)
  })

  it('flags 400 as non-retryable', () => {
    const err = makeAxiosError(400, { detail: 'Bad input' })
    const result = extractApiError(err, 'es')
    expect(result.isRetryable).toBe(false)
  })

  it('handles raw Error', () => {
    const err = new Error('oops')
    const result = extractApiError(err, 'es')
    expect(result.code).toBe('UNKNOWN_ERROR')
    expect(result.message).toBe('oops')
    expect(result.isRetryable).toBe(false)
  })

  it('handles non-Error thrown values', () => {
    const result = extractApiError('plain string', 'es')
    expect(result.code).toBe('UNKNOWN_ERROR')
    expect(result.message).toBe('plain string')
  })
})
