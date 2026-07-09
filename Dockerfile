# Container image for datasaudi-mcp — a stdio MCP server.
# Also used by Glama (https://glama.ai/mcp) to run and introspect the server.
FROM python:3.12-slim

WORKDIR /app

# Install the package from the source in this repo.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# The server speaks MCP over stdio (the default transport). Clients launch it
# as a subprocess and talk over stdin/stdout — no port is exposed.
ENTRYPOINT ["datasaudi-mcp"]
