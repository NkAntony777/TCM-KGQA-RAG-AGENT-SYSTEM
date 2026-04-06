# TCM Skill Design Guide

## Purpose

This project uses local skills as compact operating manuals for the agent. A good skill should tell the agent when to trigger, what evidence to look for first, which tool to call, and when to stop.

## Rules

1. Keep the frontmatter minimal: only `name` and `description`.
2. Put trigger signals in the `description`, because the scanner only reads `name` and `description`.
3. Keep each skill narrow. One skill should solve one retrieval intention, not a whole QA workflow.
4. Prefer domain verbs over generic names.
5. Default to local TCM tools first. Use external verification only when the user explicitly asks or local evidence is insufficient.
6. Write imperative instructions. Do not explain concepts the model already knows.
7. Require source-aware outputs when the skill is about origin or citation.

## Recommended Skill Shape

- Goal: one sentence implicit in the description.
- `## Preferred Tools`: strongest path first, fallback second.
- `## Workflow`: 4 to 7 short steps.
- `## Output Focus`: what the skill must preserve in the returned evidence.
- `## Stop Rule`: when evidence is sufficient, stop and hand back to synthesis.

These section titles are intentionally fixed because the runtime skill registry parses them directly for the deep planner.

## Naming Pattern

Use lowercase hyphen-case and align names with planner skill ids when possible.

Examples:
- `route-tcm-query`
- `read-formula-origin`
- `compare-formulas`
- `find-case-reference`

## Anti-patterns

- One giant knowledge-base skill that mixes routing, PDF handling, Excel handling, and answer synthesis.
- Skills whose description is too generic, such as “help answer user questions”.
- Skills that do not tell the agent what the first tool call should be.
- Skills that omit stop conditions and therefore encourage endless retrieval.
- Skills unrelated to the domain that pollute the snapshot.

## Current Preferred Skill Set

- `route-tcm-query`
- `read-formula-composition`
- `read-formula-origin`
- `compare-formulas`
- `find-case-reference`
- `trace-source-passage`
- `external-source-verification`
