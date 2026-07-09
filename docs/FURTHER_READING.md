# Further reading

A harshly-filtered list of the resources that actually shaped how `datasaudi-mcp`
is designed. No research papers, no `hello-world` tutorials — engineering blogs,
official docs, and real code. Every link here was verified live and says what the
note claims.

If you read nothing else, read the three ⭐ in Tier 1. They contain most of the
ideas behind every design decision in this repo.

## ⭐ Tier 1 — the three that shaped this project

- **[Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)**
  — Anthropic Engineering (Sep 2025). The constitution. Consolidate many narrow tools
  into a few workhorses; "pagination, range selection, filtering, and/or truncation with
  sensible default parameter values"; "prompt-engineer your error responses to communicate
  specific and actionable improvements, not opaque error codes"; return only high-signal
  information. Nearly every rule in this repo (the 3-tool surface, R5, R13, R21, R22) traces
  here.

- **[Code execution with MCP: building more efficient agents](https://www.anthropic.com/engineering/code-execution-with-mcp)**
  — Anthropic Engineering (Nov 2025). Why context is finite and *more data makes the model
  worse* — the justification for returning compact stubs, not everything. "Tool definitions
  overload the context window." The "pull, not push" mindset behind guided discovery
  (`list_cubes` → `describe_cube` → `query_cube`).

- **[Lessons Learned Writing an MCP Server for PostgreSQL](https://www.pgedge.com/blog/lessons-learned-writing-an-mcp-server-for-postgresql)**
  — Dave Page, pgEdge (Feb 2026). The practitioner counterpart to Anthropic's theory. Where
  the default row limit, the JSON→compact token-saving idea, and the offset "more available"
  signal come from — a real engineer writing down what bit them. Short, concrete.

## Tier 2 — when you build your own MCP server

- **[Postgres MCP Pro (crystaldba/postgres-mcp)](https://github.com/crystaldba/postgres-mcp)**
  — Read its `server.py`, not just the README. The cleanest real example of the "few
  workhorse tools" pattern (discover → introspect → execute, plus differentiated
  index-tuning tools). This repo's 3-tool spine is modeled on its shape. Note its one
  weakness — `execute_sql` has no row cap — which is exactly the mistake `query_cube`'s
  R22 byte-budget avoids.

- **[MCP official docs — Tools](https://modelcontextprotocol.io/docs/concepts/tools)**
  and **[Pagination](https://modelcontextprotocol.io/specification/2025-06-18/server/utilities/pagination)**
  — the canonical protocol reference. Key gotcha it makes explicit: the spec's cursor
  pagination is for `tools/list` / `resources/list`, **not** for tool-call *results* — which
  is why `list_cubes`/`query_cube` use their own offset+completeness envelope instead of a
  cursor.

## Tier 3 — the "silent failure" idea (the deep cut)

The single idea behind R6b, R21, and R22 is **"silent tool truncation"** — a model handed a
partial result that it treats as complete, because nothing told it the result was partial.
Search that phrase ("silent tool truncation", "the bug that makes agents lie") and read a
current, well-argued piece. (No single URL is pinned here deliberately: verify any specific
article yourself before trusting it — the concept is durable, individual blog posts are not.)

---

*This project was built probe-first and validated live in a real MCP client; several rules
(the cut syntax, the 1MB byte wall, the Arabic byte-weight) come from measuring the live
API and client, not from any document. When in doubt, measure.*
