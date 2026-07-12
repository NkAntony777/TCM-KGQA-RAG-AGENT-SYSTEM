import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { ChatInput } from '@/components/chat/ChatInput'

describe('ChatInput', () => {
  const defaultProps = {
    disabled: false,
    mode: 'quick' as const,
    onModeChange: jest.fn(),
    fullEvidenceMode: false,
    onFullEvidenceModeChange: jest.fn(),
    onSend: jest.fn(),
  }

  beforeEach(() => {
    jest.clearAllMocks()
  })

  it('renders mode buttons and full evidence toggle', () => {
    render(<ChatInput {...defaultProps} />)

    expect(screen.getByRole('button', { name: /快速模式/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /深度模式/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /精简证据/ })).toBeInTheDocument()
  })

  it('switches mode when clicking mode buttons', async () => {
    render(<ChatInput {...defaultProps} />)

    await userEvent.click(screen.getByRole('button', { name: /深度模式/ }))
    expect(defaultProps.onModeChange).toHaveBeenCalledWith('deep')
  })

  it('toggles full evidence mode', async () => {
    render(<ChatInput {...defaultProps} />)

    await userEvent.click(screen.getByRole('button', { name: /精简证据/ }))
    expect(defaultProps.onFullEvidenceModeChange).toHaveBeenCalledWith(true)
  })

  it('displays full evidence mode label when enabled', () => {
    render(<ChatInput {...defaultProps} fullEvidenceMode={true} />)

    expect(screen.getByRole('button', { name: /全证据模式/ })).toBeInTheDocument()
    expect(screen.getByText(/全证据模式：把所有证据完整送入 LLM/)).toBeInTheDocument()
  })

  it('sends message when clicking send button', async () => {
    render(<ChatInput {...defaultProps} />)

    const textarea = screen.getByPlaceholderText(/输入你的问题/)
    await userEvent.type(textarea, '六味地黄丸的组成')
    await userEvent.click(screen.getByRole('button', { name: /发送/ }))

    expect(defaultProps.onSend).toHaveBeenCalledWith('六味地黄丸的组成')
  })

  it('sends message on Ctrl+Enter', async () => {
    render(<ChatInput {...defaultProps} />)

    const textarea = screen.getByPlaceholderText(/输入你的问题/)
    await userEvent.type(textarea, '你好')
    fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true })

    expect(defaultProps.onSend).toHaveBeenCalledWith('你好')
  })

  it('disables send button when input is empty', () => {
    render(<ChatInput {...defaultProps} />)

    expect(screen.getByRole('button', { name: /发送/ })).toBeDisabled()
  })

  it('disables input when disabled prop is true', () => {
    render(<ChatInput {...defaultProps} disabled={true} />)

    expect(screen.getByPlaceholderText(/输入你的问题/)).toBeDisabled()
    expect(screen.getByRole('button', { name: /发送/ })).toBeDisabled()
  })
})
