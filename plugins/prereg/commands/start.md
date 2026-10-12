---
description: Registrálj egy systematic review-t PROSPERO-ban vagy OSF Registries-ben a böngészőn keresztül — útvonal, hasonló regisztrációk, három ellenőrzési kör, két jóváhagyási kapu, utána a composer / validator / metaANAL / praxist terve
allowed-tools: Bash, Read, Write, Edit, Glob, Grep, Agent, Skill, AskUserQuestion, mcp__Claude_Browser__navigate, mcp__Claude_Browser__read_page, mcp__Claude_Browser__find, mcp__Claude_Browser__form_input, mcp__Claude_Browser__computer, mcp__Claude_Browser__get_page_text, mcp__Claude_Browser__javascript_tool, mcp__Claude_Browser__tabs_context, mcp__Claude_Browser__tabs_create, mcp__Claude_Browser__preview_start
---

Start a registration run in THIS conversation. Request: $ARGUMENTS

1. Load the `prereg:prereg` skill with the Skill tool.
2. Follow `${CLAUDE_PLUGIN_ROOT}/agents/prereg.md` from Phase 0 step by step. Do not hand the whole run to a subagent: its two user gates (content approval, and submission approval) need the user's answers in chat. The only subagent is the Pass-2 reviewer.
3. If the request already contains criteria, write them into `prereg/<slug>/spec.json` and start at Phase 1 (routing). If it contains none, start at Phase 0 and ask for them.

Never submit a registration without the Gate B answer for that specific registration.
