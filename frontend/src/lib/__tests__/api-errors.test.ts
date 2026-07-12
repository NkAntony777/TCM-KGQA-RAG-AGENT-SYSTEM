import { createSession, parseSseBlock, renameSession, request, streamChat } from '@/lib/api'
import { SseEventSchema } from '@/lib/apiSchemas'

function createMockReader(chunks: string[]) {
  let index = 0
  return {
    read: jest.fn(async () => {
      if (index >= chunks.length) {
        return { done: true, value: undefined }
      }
      const value = new TextEncoder().encode(chunks[index])
      index += 1
      return { done: false, value }
    }),
    releaseLock: jest.fn(),
  }
}

function mockSseFetch(chunks: string[]) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: true,
    status: 200,
    body: {
      getReader: () => createMockReader(chunks),
    },
  } as unknown as Response)
  global.fetch = fetchMock
  return fetchMock
}

function streamPayload() {
  return { message: 'hi', session_id: 'session-1', mode: 'quick' as const }
}

describe('request error paths', () => {
  beforeEach(() => {
    jest.restoreAllMocks()
  })

  it('throws response text for non-2xx responses', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      text: jest.fn().mockResolvedValue('bad request'),
    } as unknown as Response)

    await expect(request('/bad-request')).rejects.toThrow('bad request')
  })

  it('propagates fetch network errors', async () => {
    const networkError = new Error('network down')
    global.fetch = jest.fn().mockRejectedValue(networkError)

    await expect(request('/network-error')).rejects.toBe(networkError)
  })

  it('throws JSON parse errors for invalid JSON responses', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockRejectedValue(new SyntaxError('invalid json')),
    } as unknown as Response)

    await expect(request('/invalid-json')).rejects.toThrow(SyntaxError)
  })
})

describe('streamChat error paths', () => {
  beforeEach(() => {
    jest.restoreAllMocks()
  })

  it('throws when the SSE stream emits an error event', async () => {
    mockSseFetch(['event: error\ndata: {"error":"stream failed"}\n\n'])
    const onEvent = jest.fn()

    await expect(streamChat(streamPayload(), { onEvent })).rejects.toThrow('stream failed')
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('ignores malformed SSE blocks without data safely', async () => {
    mockSseFetch(['event: token\n\n'])
    const onEvent = jest.fn()

    await streamChat(streamPayload(), { onEvent })

    expect(parseSseBlock('event: token')).toBeNull()
    expect(onEvent).not.toHaveBeenCalled()
  })

  it('defaults SSE blocks with missing event lines to token events', async () => {
    mockSseFetch(['data: {"content":"implicit token"}\n\n'])
    const onEvent = jest.fn()

    await streamChat(streamPayload(), { onEvent })

    expect(onEvent).toHaveBeenCalledWith({
      event: 'token',
      data: { content: 'implicit token' },
    })
  })
})

describe('session API error paths', () => {
  beforeEach(() => {
    jest.restoreAllMocks()
  })

  it('throws response text when createSession receives a 500', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      text: jest.fn().mockResolvedValue('create failed'),
    } as unknown as Response)

    await expect(createSession('new session')).rejects.toThrow('create failed')
  })

  it('throws malformed JSON errors from renameSession', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: jest.fn().mockRejectedValue(new SyntaxError('rename json failed')),
    } as unknown as Response)

    await expect(renameSession('session-1', 'new title')).rejects.toThrow(SyntaxError)
  })
})

describe('SSE schema validation', () => {
  it('accepts valid token events', () => {
    const result = SseEventSchema.safeParse({
      event: 'token',
      data: { content: 'hello' },
    })

    expect(result.success).toBe(true)
  })

  it('rejects events with missing event fields', () => {
    const result = SseEventSchema.safeParse({
      data: { content: 'hello' },
    })

    expect(result.success).toBe(false)
  })

  it('handles malformed data payloads without throwing', () => {
    expect(() => {
      SseEventSchema.safeParse({
        event: 'token',
        data: 'not-an-object-payload',
      })
    }).not.toThrow()
  })
})
