---
description: Explore and understand codebase architecture and patterns using the observer agent
allowed-tools: Agent
---

🚨 CRITICAL: You MUST delegate this work to agents. DO NOT explore code or write documentation yourself.

Explore and understand the codebase, then optionally update documentation.

Focus area: $ARGUMENTS

## MANDATORY Workflow

**MANDATORY STEP 1: Invoke the observer agent**

Use the Task tool to delegate exploration to the observer agent:
```
Task(subagent_type='observer', prompt='Explore and understand codebase architecture and patterns. Focus: $ARGUMENTS')
```

**What you MUST do in Step 1:**
- ✅ Use the Task tool with subagent_type='observer'
- ✅ Pass the focus area to the agent
- ✅ Wait for the agent to complete its exploration
- ✅ Review the agent's findings

**What you MUST NOT do in Step 1:**
- ❌ Explore the codebase yourself
- ❌ Read code files directly to understand patterns
- ❌ Analyze architecture on your own
- ❌ Skip the agent and provide your own observations

---

**CONDITIONAL STEP 2: Invoke the docs-writer agent (if needed)**

After reviewing the observer's findings, if significant patterns or architectural decisions were discovered that aren't yet documented:

```
Task(subagent_type='docs-writer', prompt='Update documentation based on these findings: [summary of observer findings]')
```

**What you MUST do in Step 2 (if applicable):**
- ✅ Use the Task tool with subagent_type='docs-writer'
- ✅ Pass the observer's findings to the docs-writer agent
- ✅ Wait for the agent to update documentation

**What you MUST NOT do in Step 2:**
- ❌ Write or edit documentation files yourself
- ❌ Skip the docs-writer agent and update docs directly
- ❌ Provide documentation content instead of using the agent

---

**MANDATORY STEP 3: Report findings**

After agents complete their work:
- ✅ Summarize what the observer agent discovered
- ✅ Report any documentation updates made by the docs-writer agent (if invoked)

**Your role:** You are DELEGATING to agents, not exploring code or writing documentation yourself.
