import { render, screen } from '@testing-library/react'
import { ChatMessage } from '@/components/chat/ChatMessage'

jest.mock('react-markdown', () => ({
  __esModule: true,
  default: ({ children }: { children: string }) => <>{children}</>,
}))

jest.mock('remark-gfm', () => () => {})

const evidence = [
  { source_type: 'graph', source: 'book', snippet: 'evidence snippet', score: null },
]
const defaultProps = {
  toolCalls: [],
  retrievals: [],
  evidence: [],
  plannerSteps: [],
  deepTrace: [],
  notes: [],
  citations: [],
  skills: [],
}
const propsWithEvidence = { ...defaultProps, evidence }

describe('ChatMessage', () => {
  it('renders user message content', () => {
    render(<ChatMessage role="user" content="用户消息" {...defaultProps} />)
    expect(screen.getByText('用户消息')).toBeInTheDocument()
  })

  it('does not render assistant-specific elements for user message', () => {
    render(
      <ChatMessage role="user" content="hi" evidence={evidence} {...defaultProps} />
    )
    expect(screen.queryByText(/证据/)).not.toBeInTheDocument()
    expect(screen.queryByText('正在思考...')).not.toBeInTheDocument()
  })

  it('renders assistant message content', () => {
    render(
      <ChatMessage role="assistant" content="助手回答" {...defaultProps} />
    )
    expect(screen.getByText('助手回答')).toBeInTheDocument()
  })

  it('shows placeholder when assistant content is empty and not active', () => {
    render(
      <ChatMessage
        role="assistant"
        content=""
        isActive={false}
        {...defaultProps}
      />
    )
    expect(screen.getByText('正在思考...')).toBeInTheDocument()
  })

  it('renders evidence cards when evidence is present', () => {
    render(
      <ChatMessage
        role="assistant"
        content="回答"
        {...propsWithEvidence}
      />
    )
    expect(screen.getByText(/证据 1 条/)).toBeInTheDocument()
    expect(screen.getByText('evidence snippet')).toBeInTheDocument()
  })

  it('does not render evidence for user messages even when evidence is passed', () => {
    render(
      <ChatMessage role="user" content="hello" evidence={evidence} {...defaultProps} />
    )
    expect(screen.queryByText(/证据/)).not.toBeInTheDocument()
  })
})
