# Security Policy

## Supported versions

Only the latest released version of `datasaudi-mcp` receives fixes. Please upgrade before reporting (`uvx datasaudi-mcp` always runs the newest release, or `pip install --upgrade datasaudi-mcp`).

## Reporting a vulnerability

Please report suspected vulnerabilities **privately** — do not open a public issue for anything security-sensitive.

- Preferred: open a [private security advisory](https://github.com/mohsinmshabbir/datasaudi-mcp/security/advisories/new) on GitHub.
- Or email **mohsinmshabbir@icloud.com** with details and, if possible, steps to reproduce.

I'll acknowledge within a few days and keep you posted on a fix.

## Scope — what this project actually does

Knowing the surface helps you gauge risk:

- **No credentials.** The DataSaudi API is keyless; the server stores and transmits no secrets, tokens, or user data.
- **Read-only.** It only issues GET queries to the public DataSaudi API (`api.datasaudi.sa`). It never writes anywhere and has no database.
- **Runs as a local subprocess.** MCP clients launch it over stdio; it opens no network listener and exposes no port.
- **Outbound HTTP only**, to the single DataSaudi host.

Given that, the most relevant classes of report are things like: a crafted API response that could crash or mislead the client, a dependency vulnerability, or a way the tool could be made to return confidently wrong data (this project's whole design goal is to *never* silently mislead — a reproducible case where it does is very much in scope).
