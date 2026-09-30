#!/bin/sh
# End-to-end check of the rendered MCP interface: initialize, list the tools,
# call a skill, and read one of its resources. Requires `jq`.
set -eu

BIN=${BIN:-./target/debug/custom-skills-mcp}
[ -x "$BIN" ] || { echo "build first: cargo build --locked" >&2; exit 1; }
command -v jq >/dev/null || { echo "smoke test requires jq" >&2; exit 1; }

out=$(
  {
    printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"smoke","version":"0.1.0"}}}'
    printf '%s\n' '{"jsonrpc":"2.0","method":"notifications/initialized","params":{}}'
    printf '%s\n' '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}'
    printf '%s\n' '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"skill_catalog","arguments":{}}}'
    printf '%s\n' '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"skill-authoring","arguments":{}}}'
    printf '%s\n' '{"jsonrpc":"2.0","id":5,"method":"tools/call","params":{"name":"skill_resource","arguments":{"skill":"skill-authoring","path":"references/frontmatter.md"}}}'
  } | "$BIN"
)

# `sh`'s echo mangles the backslash escapes inside JSON strings; printf does not.
emit() { printf '%s\n' "$1"; }

check() {
  emit "$out" | jq -e "$1" >/dev/null || {
    emit "FAIL: $2" >&2
    emit "$out" >&2
    exit 1
  }
  emit "ok: $2"
}

check 'select(.id==1) | .result.serverInfo.name == "custom-skills-mcp"' 'initialize'
check 'select(.id==2) | [.result.tools[].name] | index("skill_catalog") != null' 'tools/list has skill_catalog'
check 'select(.id==2) | [.result.tools[].name] | index("skill-authoring") != null' 'tools/list has skill-authoring'
check 'select(.id==3) | .result.isError != true and ((.result.content[0].text | fromjson).count > 0)' 'skill_catalog'
check 'select(.id==4) | .result.isError != true and (.result.content[0].text | test("Authoring a skill"))' 'skill call returns its body'
check 'select(.id==5) | .result.isError != true and (.result.content[0].text | test("Frontmatter contract"))' 'skill_resource'

# Protocol 2026-07-28 has no initialize: each request carries the version in
# `_meta`, and a list result must carry `ttlMs` and `cacheScope`. A client that
# validates against that schema rejects a tools/list missing either.
out=$(
  printf '%s\n' '{"jsonrpc":"2.0","id":6,"method":"tools/list","params":{"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28","io.modelcontextprotocol/clientCapabilities":{}}}}' \
    | "$BIN"
)
check 'select(.id==6) | (.result.ttlMs | type) == "number" and (.result.cacheScope | IN("public", "private")) and (.result.tools | length) > 0' 'tools/list under 2026-07-28 has ttlMs and cacheScope'

emit "smoke passed: $(emit "$out" | jq -r 'select(.id==6) | .result.tools | length') tools"
