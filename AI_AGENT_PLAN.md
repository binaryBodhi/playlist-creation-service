# Turning This Project Into an AI Agent

## Current State

This project already has the core of an LLM-powered assistant, but not a full agent.

### What is already present

- Package entrypoint: `__main__.py` starts Jarvis mode and loads environment variables.
- Natural-language interface: `jarvis/jarvis_cli.py` runs an interactive REPL and sends user text to the model.
- Tool schema: `jarvis/jarvis_tools.json` exposes structured tool definitions to the model.
- Tool selection: `jarvis/llm_helpers.py` asks the model to choose a tool call from a fixed set.
- Tool execution: `safe_invoke_tool()` dispatches the chosen tool call into real Python functions.
- Domain actions: `apis/api.py` contains concrete Spotify operations with meaningful side effects.
- External integration: `apis/oauth.py`, `apis/utilities.py`, and `apis/spotify_helpers.py` already handle auth, API calls, batching, retries, and pagination.
- Basic safety: delete operations support `dry_run`, ownership checks, tag checks, and explicit confirmation.

### What this means

Right now the system can:

- accept a user command in plain English,
- map it to one of a few predefined actions,
- execute that action,
- summarize the result.

That is a tool-calling assistant. It is not yet an agent because it does not independently manage a goal over multiple steps.

## What is missing

To behave like an AI agent, the system needs a control loop, state, and the ability to observe and adapt.

### Missing capability 1: a planning and execution loop

Current behavior is one-shot:

1. user speaks
2. model picks one tool
3. tool runs
4. model summarizes

An agent needs:

- goal interpretation,
- plan generation,
- iterative execution,
- re-planning after each tool result,
- stop conditions.

Without that, Jarvis cannot handle tasks like:

- "Inspect this playlist, tell me what you would do, then do it if I approve."
- "Split this playlist, then clean up any empty year playlists."
- "Try the safe approach first. If there are collisions, ask me."

### Missing capability 2: explicit task state

The current code does not maintain a structured task object across turns.

An agent needs persisted state such as:

- user goal,
- current plan,
- completed steps,
- pending steps,
- tool outputs,
- approvals received,
- errors encountered.

Without task state, the system has no durable notion of progress.

### Missing capability 3: memory

The project has no short-term or long-term memory layer beyond the current prompt and Spotify token storage.

An agent usually needs:

- conversational memory for the current session,
- task memory for active goals,
- preference memory for user choices,
- optional persistent memory for repeated workflows.

Example:

- If the user says "always preview deletions first," an agent should remember that and bias toward `dry_run=True`.

### Missing capability 4: observation tools

The current tool surface is action-heavy and inspection-light. It can split and delete, but it cannot inspect enough to reason well before acting.

Useful missing tools include:

- inspect a playlist and summarize counts, years, duplicates, local tracks, and episodes,
- list playlists previously created by this tool,
- preview what split results would be without creating playlists,
- compare source and destination playlists,
- detect empty or partially created year playlists,
- explain why a deletion target matched or did not match.

An agent needs observation tools so it can decide, not just execute.

### Missing capability 5: richer policy and approval handling

The current delete flow has confirmation, but approval is embedded inside the tool and only for one operation type.

An agent needs an explicit action policy:

- which actions are safe to do autonomously,
- which actions require preview first,
- which actions always require user approval,
- how to present a plan before executing destructive steps.

### Missing capability 6: verification and recovery

The current flow executes a tool and returns the result. It does not verify whether the broader goal was actually satisfied.

An agent needs:

- post-action verification,
- retry strategy,
- fallback behavior,
- partial-failure handling,
- resumability.

Example:

- If 3 year playlists were created but 1 failed due to rate limiting, an agent should detect that, retry or explain the partial state, and continue the task intelligently.

### Missing capability 7: a broader toolset

A true agent in this domain needs more than two verbs.

The minimum tool categories are:

- inspect
- preview
- create/update
- delete
- verify
- explain

The current project mainly has create/update and delete.

### Missing capability 8: agent-oriented system prompt and operating rules

The current system prompt in `jarvis/llm_helpers.py` tells the model to map commands to tools. That is intentionally narrow.

An agent prompt needs to define:

- the role,
- decision policy,
- planning rules,
- safety rules,
- clarification rules,
- when to ask versus act,
- how to use tools iteratively,
- how to summarize execution state.

### Missing capability 9: instrumentation and evaluation

Once a system can act autonomously, observability matters.

Missing pieces:

- step-level logs,
- stored traces of model decisions,
- tool-call audit records,
- evaluation cases for safe and unsafe behaviors,
- regression tests for prompts and planners.

Without this, the system may appear agentic but be hard to trust.

## How the current pieces become an agent

The existing code is not wasted. It is already the action layer.

### Present pieces that should remain

- `jarvis/jarvis_cli.py` can remain the conversational shell.
- `jarvis/jarvis_tools.json` can remain the tool registry, but it should be expanded.
- `jarvis/llm_helpers.py` can remain the model integration layer, but it should move from single-step routing to iterative orchestration.
- `apis/api.py` is already the domain execution backend and should stay the source of truth for side effects.
- The Spotify helpers already provide the low-level substrate an agent needs to inspect and act.

### New pieces to add

- `agent/session.py`
  Maintains conversation state, active goal, plan, approvals, and execution history.

- `agent/planner.py`
  Turns a user request plus current context into a multi-step plan.

- `agent/runner.py`
  Owns the agent loop:
  plan -> choose tool -> execute -> observe result -> update plan -> continue or stop.

- `agent/policy.py`
  Centralizes rules for destructive actions, previews, and approval thresholds.

- `agent/memory.py`
  Stores session memory and optional persistent preferences.

- `agent/tools.py`
  Registers both current and new inspection/verification tools in one place.

- `agent/evals/`
  Contains behavior tests and scenario-based evaluations.

### Expanded toolset

The current domain functions should be joined by new tools such as:

- `spotify_inspect_playlist`
- `spotify_preview_split_by_year`
- `spotify_list_generated_playlists`
- `spotify_verify_split_results`
- `spotify_explain_delete_matches`
- `spotify_cleanup_empty_generated_playlists`

These are what let the agent reason before and after acting.

## What would make it an agent in practice

The transition happens when the system changes from "choose one tool for this utterance" to "own the lifecycle of a goal."

### Today

Current loop:

1. parse one user request
2. select one tool
3. execute once
4. respond

### Agent version

Target loop:

1. interpret user goal
2. inspect relevant state
3. create a plan
4. decide whether approval is required
5. execute the next tool
6. verify the result
7. update the plan
8. repeat until goal is complete or blocked
9. return a final outcome with reasoning and any remaining decisions

That loop is the real difference.

## Example: same request before and after

User request:

`Split my "Roadtrip Mix" playlist, but show me what will happen first.`

### Current project

- The model can only choose the split tool.
- There is no preview tool.
- There is no plan state.
- The system either acts immediately or asks a vague question.

### Agent version

The agent would:

1. inspect the source playlist,
2. compute the year buckets,
3. present a preview,
4. wait for approval,
5. create or update the per-year playlists,
6. verify counts,
7. summarize the result and any anomalies.

That is agent behavior because it is goal-directed, multi-step, and stateful.

## Minimum bar for calling this an AI agent

I would use this bar:

- It can decompose a request into multiple steps.
- It can choose among both observation and action tools.
- It maintains task state across those steps.
- It can verify whether the goal was achieved.
- It uses an explicit approval policy for risky actions.
- It can recover from partial failures instead of just returning an exception.

If those are in place, this project stops being a thin LLM wrapper and becomes a domain-specific Spotify agent.

## Practical implementation order

1. Add inspection and preview tools first.
2. Introduce an explicit `AgentSession` state object.
3. Replace single-step tool routing with an agent runner loop.
4. Add approval and safety policy outside the raw tool functions.
5. Add verification tools and partial-failure recovery.
6. Add memory for user preferences and repeated workflows.
7. Add logging, test scenarios, and evals.

This order matters because planning without observability and verification usually produces brittle pseudo-agents.

## Bottom Line

What is already present gives you:

- natural-language input,
- tool calling,
- real backend actions,
- basic safety primitives.

What is missing gives you:

- planning,
- state,
- memory,
- observation,
- verification,
- policy,
- recovery.

When you combine the current action layer with those missing orchestration layers, you get a real domain-specific AI agent for Spotify playlist management, not just a model that picks from two functions.
