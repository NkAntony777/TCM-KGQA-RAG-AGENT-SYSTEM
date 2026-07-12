import { act, render, screen } from '@testing-library/react'

import { AnswerTraceTimeline } from '@/components/chat/AnswerTraceTimeline'

describe('AnswerTraceTimeline', () => {
  it('renders nothing when inactive and no data', () => {
    const { container } = render(
      <AnswerTraceTimeline
        plannerSteps={[]}
        deepTrace={[]}
        evidenceBundle={undefined}
        isActive={false}
      />
    )
    expect(container.firstChild).toBeNull()
  })

  it('shows running step based on latest planner_step stage', () => {
    render(
      <AnswerTraceTimeline
        route={{
          route: 'hybrid',
          reason: 'test',
          status: 'ok',
          final_route: 'hybrid',
          executed_routes: ['graph', 'retrieval'],
        }}
        plannerSteps={[
          { stage: 'route_decision', label: '分析查询并选择路由', detail: 'query' },
          { stage: 'route_search', label: '执行首轮检索', detail: 'route=hybrid' },
          { stage: 'retrieval', label: '执行文件优先检索', detail: 'FFSR' },
        ]}
        deepTrace={[]}
        evidenceBundle={undefined}
        qaMode="quick"
        isActive={true}
      />
    )

    expect(screen.getByText(/当前：检索执行/)).toBeInTheDocument()
    expect(screen.getByText(/执行文件优先检索/)).toBeInTheDocument()
  })

  it('marks retrieval and coverage done when evidence bundle is present', () => {
    render(
      <AnswerTraceTimeline
        route={{
          route: 'hybrid',
          reason: 'test',
          status: 'ok',
          final_route: 'hybrid',
          executed_routes: ['graph'],
        }}
        plannerSteps={[
          { stage: 'route_decision', label: '分析查询并选择路由', detail: 'query' },
          { stage: 'answer_synthesis', label: '生成最终答案', detail: 'quick' },
        ]}
        deepTrace={[]}
        evidenceBundle={{
          coverage: { factual_count: 5, evidence_path_count: 3, gaps: [] },
          factual_evidence: [],
        }}
        qaMode="quick"
        isActive={true}
      />
    )

    // Step cards are rendered with titles; step 5 should be running (answer_synthesis)
    expect(screen.getByText(/当前：证据约束生成/)).toBeInTheDocument()
    expect(screen.getByText(/证据：5 条事实/)).toBeInTheDocument()
  })

  it('shows elapsed time when active', () => {
    jest.useFakeTimers()
    jest.setSystemTime(new Date('2024-01-01T00:00:00Z'))
    render(
      <AnswerTraceTimeline
        route={undefined}
        plannerSteps={[{ stage: 'route_decision', label: '分析查询并选择路由', detail: 'query' }]}
        deepTrace={[]}
        evidenceBundle={undefined}
        qaMode="quick"
        isActive={true}
      />
    )

    act(() => {
      jest.advanceTimersByTime(2500)
    })
    expect(screen.getByText(/2s/)).toBeInTheDocument()
    jest.setSystemTime(Date.now())
    jest.useRealTimers()
  })

  it('renders deep mode specific labels', () => {
    render(
      <AnswerTraceTimeline
        route={{
          route: 'hybrid',
          reason: 'test',
          status: 'ok',
          final_route: 'hybrid',
          executed_routes: ['graph'],
        }}
        plannerSteps={[]}
        deepTrace={[
          { step: 1, round: 1, action_index: 1, skill: 'read-formula-origin', status: 'ok', why_this_step: '补出处' },
        ]}
        evidenceBundle={{
          coverage: { factual_count: 2, evidence_path_count: 1, gaps: [] },
          factual_evidence: [],
        }}
        qaMode="deep"
        isActive={false}
      />
    )

    expect(screen.getByText(/Deep 补证据/)).toBeInTheDocument()
    expect(screen.getByText(/1 个 deep trace 步骤/)).toBeInTheDocument()
  })
})
