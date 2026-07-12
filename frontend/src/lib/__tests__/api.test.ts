import { streamChat } from '@/lib/api'

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

describe('streamChat', () => {
  beforeEach(() => {
    jest.restoreAllMocks()
  })

  it('sends correct payload including full_evidence_mode', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => createMockReader([
          'event: done\ndata: {"content":"answer"}\n\n',
        ]),
      },
    } as unknown as Response)
    global.fetch = fetchMock

    const events: any[] = []
    await streamChat(
      {
        message: 'test',
        session_id: 'session-1',
        mode: 'quick',
        top_k: 12,
        full_evidence_mode: true,
      },
      {
        onEvent: (event) => events.push(event),
      }
    )

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [, init] = fetchMock.mock.calls[0]
    const body = JSON.parse(init.body as string)
    expect(body.message).toBe('test')
    expect(body.session_id).toBe('session-1')
    expect(body.mode).toBe('quick')
    expect(body.top_k).toBe(12)
    expect(body.full_evidence_mode).toBe(true)
    expect(body.stream).toBe(true)
  })

  it('emits parsed SSE events', async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      body: {
        getReader: () => createMockReader([
          'event: token\ndata: {"content":"Hello"}\n\n',
          'event: token\ndata: {"content":" world"}\n\n',
          'event: done\ndata: {"content":"Hello world"}\n\n',
        ]),
      },
    } as unknown as Response)
    global.fetch = fetchMock

    const events: any[] = []
    await streamChat(
      {
        message: 'hi',
        session_id: 'session-1',
        mode: 'quick',
      },
      {
        onEvent: (event) => events.push(event),
      }
    )

    expect(events).toHaveLength(3)
    expect(events[0]).toEqual({ event: 'token', data: { content: 'Hello' } })
    expect(events[1]).toEqual({ event: 'token', data: { content: ' world' } })
    expect(events[2]).toEqual({ event: 'done', data: { content: 'Hello world' } })
  })

  it('throws on non-ok response', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
    } as unknown as Response)

    await expect(
      streamChat(
        { message: 'hi', session_id: 'session-1', mode: 'quick' },
        { onEvent: jest.fn() }
      )
    ).rejects.toThrow('Chat request failed: 500')
  })
})
