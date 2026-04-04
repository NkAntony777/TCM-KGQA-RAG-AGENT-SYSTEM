# Files Are All You Need And ChromaFs Notes

Date: 2026-04-04

## References

1. Piskala. *From Everything-is-a-File to Files-Are-All-You-Need: How Unix Philosophy Informs the Design of Agentic AI Systems*.
   Link: https://arxiv.org/abs/2601.11672

2. Mintlify engineering blog. *How we built a virtual filesystem for our assistant*.
   Link: https://www.mintlify.com/blog/how-we-built-a-virtual-filesystem-for-our-assistant

3. Related direction: *Everything is Context: Agentic File System Abstraction for Context Engineering*.
   Public discussions and follow-on implementations emphasize the same pattern: use file-system-like abstractions to organize context and tool access for agents.

## Shared Design Theme

These works argue that agent systems become easier to scale and reason about when heterogeneous resources are presented through a unified, browseable abstraction.

Core principles:

- unify access patterns
- prefer read-only exploration
- make context construction explicit
- let agents navigate evidence incrementally instead of receiving one flat blob

## Why This Matters For This Project

This TCM system already has multiple evidence backends:

- runtime graph in SQLite
- Nebula graph
- retrieval chunks
- external QA vector database
- source-book text evidence

Without a unifying abstraction, a deep-mode agent will either:

- overuse one tool repeatedly
- produce brittle prompt-based retrieval behavior
- or couple itself too tightly to backend-specific APIs

## Best Reusable Ideas

### 1. Evidence paths over raw backend calls

Instead of making the agent directly think in terms of SQL tables, graph queries, or vector DB calls, expose stable logical paths such as:

- `entity://六味地黄丸/使用药材`
- `entity://六味地黄丸/功效`
- `symptom://脉微/syndrome_chain`
- `qa://六味地黄丸/similar`

### 2. Read-only exploration by default

The agent should read evidence, not modify graph state.

### 3. Small tools that feel like file operations

Minimal useful operations:

- list evidence paths
- read evidence path
- search evidence text

### 4. Context assembly as a first-class subsystem

Separate:

- retrieval strategy
- evidence object construction
- evidence path navigation
- answer-context assembly

## Recommended Adoption Strategy

Do not implement a full virtual filesystem first.

Instead:

1. Add structured retrieval strategy
2. Add logical evidence paths
3. Add read/list/search wrappers over those paths
4. Later, if useful, add shell-like browsing semantics

## Applicability Verdict

High applicability.

Not because this project should literally become a filesystem, but because the evidence layer should be:

- unified
- inspectable
- composable
- agent-friendly

That is the real transferable insight from both the paper and ChromaFs.
