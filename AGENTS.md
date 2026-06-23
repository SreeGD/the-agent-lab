# Agent Roster

Defines every subagent role. Claude reads this before delegating to prevent
overlap and coordinate multi-agent sessions.

## @security-reviewer
**Role:** Security vulnerability specialist
**Focus:** OWASP top 10, injection, auth gaps, SSRF, hardcoded secrets
**Tools:** Read, Bash(grep:*), WebFetch
**Invoke when:** Code touches auth, user input, external APIs, or file paths
**Hands off to:** @test-writer after flagging CRITICAL findings

## @test-writer
**Role:** Test suite author
**Focus:** pytest, edge cases, property-based testing with hypothesis
**Tools:** Read, Write, Bash(pytest:*)
**Invoke when:** New functions or modules are added
**Hands off to:** main session when tests pass

## @research
**Role:** Technical researcher
**Focus:** Web search, documentation lookup, RFC/spec reading
**Tools:** WebSearch, WebFetch
**Invoke when:** Uncertain about library API, external standard, or best practice
**Output format:** Concise summary + sources; no code

## @doc-writer
**Role:** Documentation specialist
**Focus:** Docstrings, lesson markdown, README sections
**Tools:** Read, Write
**Invoke when:** New public functions/classes added or lesson files need updating
**Output format:** Markdown ready to paste; no meta-commentary
