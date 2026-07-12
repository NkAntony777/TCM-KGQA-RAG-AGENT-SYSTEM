import { act, renderHook, waitFor } from '@testing-library/react'
import { useSessionState } from '@/lib/useSessionState'

jest.mock('@/lib/api', () => ({
  streamChat: jest.fn(),
  createSession: jest.fn(),
  renameSession: jest.fn(),
  listSessions: jest.fn(),
  getSessionHistory: jest.fn(),
  getSessionTokens: jest.fn(),
  deleteSession: jest.fn(),
  compressSession: jest.fn(),
}))

import {
  streamChat,
  createSession,
  renameSession,
  listSessions,
  getSessionHistory,
  getSessionTokens,
} from '@/lib/api'

function mockSession(id = 'session-1', title = '新会话') {
  return { id, title, created_at: Date.now(), updated_at: Date.now(), message_count: 0 }
}

const emptyHistory = { id: 'session-1', title: 'test', messages: [] }
const emptyTokens = { system_tokens: 0, message_tokens: 0, total_tokens: 0 }

beforeEach(() => {
  jest.clearAllMocks()
  ;(createSession as jest.Mock).mockResolvedValue(mockSession())
  ;(listSessions as jest.Mock).mockResolvedValue([])
  ;(getSessionHistory as jest.Mock).mockResolvedValue(emptyHistory)
  ;(getSessionTokens as jest.Mock).mockResolvedValue(emptyTokens)
})

describe('useSessionState', () => {
  it('calls streamChat with correct parameters', async () => {
    const mockStreamChat = streamChat as jest.Mock
    mockStreamChat.mockResolvedValue(undefined)

    const { result } = renderHook(() =>
      useSessionState({ qaMode: 'quick', fullEvidenceMode: false })
    )

    await act(async () => {
      await result.current.sendMessage('test message')
    })

    expect(mockStreamChat).toHaveBeenCalledTimes(1)
    expect(mockStreamChat).toHaveBeenCalledWith(
      {
        message: 'test message',
        session_id: 'session-1',
        mode: 'quick',
        top_k: 12,
        full_evidence_mode: false,
      },
      expect.objectContaining({ onEvent: expect.any(Function) }),
      expect.objectContaining({ signal: expect.any(AbortSignal) })
    )
  })

  it('sets isStreaming=true during stream lifecycle', async () => {
    const mockStreamChat = streamChat as jest.Mock
    let resolveStream!: () => void
    mockStreamChat.mockImplementation(
      () => new Promise<void>((resolve) => { resolveStream = resolve })
    )

    const { result } = renderHook(() =>
      useSessionState({ qaMode: 'quick', fullEvidenceMode: false })
    )

    await act(async () => {
      result.current.sendMessage('test')
      await Promise.resolve()
    })

    expect(result.current.isStreaming).toBe(true)

    await act(async () => {
      resolveStream()
      await Promise.resolve()
    })

    await waitFor(() => {
      expect(result.current.isStreaming).toBe(false)
    })
  })

  it('handles stream errors', async () => {
    const mockStreamChat = streamChat as jest.Mock
    mockStreamChat.mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() =>
      useSessionState({ qaMode: 'quick', fullEvidenceMode: false })
    )

    await act(async () => {
      await result.current.sendMessage('test')
    })

    expect(result.current.isStreaming).toBe(false)
    expect(mockStreamChat).toHaveBeenCalled()
  })

  it('creates a new session', async () => {
    const mockCreateSession = createSession as jest.Mock
    const mockListSessions = listSessions as jest.Mock
    const newSession = mockSession('session-1')
    mockCreateSession.mockResolvedValue(newSession)
    mockListSessions.mockResolvedValue([newSession])

    const { result } = renderHook(() =>
      useSessionState({ qaMode: 'quick', fullEvidenceMode: false })
    )

    await act(async () => {
      await result.current.createNewSession()
    })

    expect(mockCreateSession).toHaveBeenCalledTimes(1)
    expect(result.current.sessions).toEqual([newSession])
    expect(result.current.currentSessionId).toBe('session-1')
  })

  it('renames the current session', async () => {
    const mockRenameSession = renameSession as jest.Mock
    const mockListSessions = listSessions as jest.Mock
    mockRenameSession.mockResolvedValue(mockSession('session-1', '新标题'))

    const { result } = renderHook(() =>
      useSessionState({ qaMode: 'quick', fullEvidenceMode: false })
    )

    await act(async () => {
      await result.current.createNewSession()
    })

    await act(async () => {
      await result.current.renameCurrentSession('新标题')
    })

    expect(mockRenameSession).toHaveBeenCalledWith('session-1', '新标题')
    expect(mockListSessions).toHaveBeenCalled()
  })
})
