---
description: Find and prove the root cause of a bug using the debugger agent
allowed-tools: Agent
---

🚨 CRITICAL: You MUST delegate this work to the debugger agent. DO NOT debug the issue yourself.

Find and prove the root cause of this bug: $ARGUMENTS

## MANDATORY Workflow

**STEP 1: Invoke the debugger agent**

Use the Task tool to delegate to the debugger agent:
```
Task(subagent_type='debugger', prompt='Find and prove the root cause of: $ARGUMENTS')
```

**What you MUST do:**
- ✅ Use the Task tool with subagent_type='debugger'
- ✅ Pass the bug description and focus area to the agent
- ✅ Wait for the agent to complete its investigation
- ✅ Report the agent's findings about the root cause

**What you MUST NOT do:**
- ❌ Debug the issue yourself
- ❌ Read code files to investigate the bug directly
- ❌ Run tests or commands to diagnose the bug
- ❌ Skip the agent and provide your own analysis

**Your role:** You are DELEGATING to an agent, not debugging yourself.
