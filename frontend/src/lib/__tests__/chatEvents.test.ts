import { applyChatStreamEvent } from '@/lib/chatEvents'
import { createMessage } from '@/lib/storeModels'

describe('applyChatStreamEvent', () => {
  const baseMessage = createMessage('assistant')

  it('sets qa mode', () => {
    const next = applyChatStreamEvent(baseMessage, {
      event: 'qa_mode',
      data: { mode: 'deep' },
    })
    expect(next.qaMode).toBe('deep')
  })

  it('sets route event', () => {
    const route = {
      route: 'hybrid',
      reason: 'test',
      status: 'ok',
      final_route: 'hybrid',
      executed_routes: ['graph', 'retrieval'],
    }
    const next = applyChatStreamEvent(baseMessage, {
      event: 'route',
      data: route,
    })
    expect(next.route).toEqual(route)
  })

  it('appends evidence items', () => {
    const items = [
      { source_type: 'graph', source: 'book', snippet: 'snippet-1' },
      { source_type: 'doc', source: 'book', snippet: 'snippet-2' },
    ]
    const next = applyChatStreamEvent(baseMessage, {
      event: 'evidence',
      data: { items },
    })
    expect(next.evidence).toHaveLength(2)
    expect(next.evidence[0].snippet).toBe('snippet-1')
  })

  it('deduplicates evidence by source_type, source and snippet', () => {
    const items = [
      { source_type: 'graph', source: 'book', snippet: 'same' },
      { source_type: 'graph', source: 'book', snippet: 'same' },
    ]
    const next = applyChatStreamEvent(baseMessage, {
      event: 'evidence',
      data: { items },
    })
    expect(next.evidence).toHaveLength(1)
  })

  it('appends planner steps', () => {
    const step = { stage: 'route_search', label: '执行首轮检索', detail: 'test' }
    const next = applyChatStreamEvent(baseMessage, {
      event: 'planner_step',
      data: { step },
    })
    expect(next.plannerSteps).toHaveLength(1)
    expect(next.plannerSteps[0]).toEqual(step)
  })

  it('appends tokens to content', () => {
    let next = applyChatStreamEvent(baseMessage, {
      event: 'token',
      data: { content: 'Hello' },
    })
    next = applyChatStreamEvent(next, {
      event: 'token',
      data: { content: ' world' },
    })
    expect(next.content).toBe('Hello world')
  })

  it('sets streamDone on done event', () => {
    const next = applyChatStreamEvent(baseMessage, {
      event: 'done',
      data: { content: 'final' },
    })
    expect(next.streamDone).toBe(true)
  })

  it('fills content from done event when empty', () => {
    const next = applyChatStreamEvent(baseMessage, {
      event: 'done',
      data: { content: 'final answer' },
    })
    expect(next.content).toBe('final answer')
  })

  it('sets evidence bundle', () => {
    const bundle = {
      coverage: { factual_count: 5, evidence_path_count: 3, gaps: [] },
      factual_evidence: [],
    }
    const next = applyChatStreamEvent(baseMessage, {
      event: 'evidence_bundle',
      data: { bundle },
    })
    expect(next.evidenceBundle).toEqual(bundle)
  })

  it('ignores unknown events', () => {
    const next = applyChatStreamEvent(baseMessage, {
      event: 'unknown_event' as any,
      data: {},
    })
    expect(next).toEqual(baseMessage)
  })
})
