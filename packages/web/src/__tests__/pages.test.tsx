import { describe, it, expect } from '@jest/globals'

describe('Facil Frontend', () => {
  it('should pass basic sanity check', () => {
    expect(true).toBe(true)
  })

  it('should have valid environment', () => {
    expect(process.env.NODE_ENV).toBeDefined()
  })

  it('should export authApi module', async () => {
    const { authApi } = await import('@/core/api/auth')
    expect(authApi).toBeDefined()
    expect(authApi.login).toBeDefined()
    expect(authApi.register).toBeDefined()
  })
})
