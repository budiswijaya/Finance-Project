---
description: Review code changes for critical issues using the code-reviewer agent
allowed-tools: Agent
---

🚨 CRITICAL: You MUST delegate this work to the code-reviewer agent. DO NOT review code yourself.

Review code changes for critical issues.

Focus area (if specified): $ARGUMENTS

## MANDATORY Workflow

**STEP 1: Invoke the code-reviewer agent**

Use the Task tool to delegate to the code-reviewer agent:
```
Task(subagent_type='code-reviewer', prompt='Review code changes for critical issues. Focus: $ARGUMENTS')
```

**What you MUST do:**
- ✅ Use the Task tool with subagent_type='code-reviewer'
- ✅ Pass any specific files or areas to review to the agent
- ✅ Wait for the agent to complete its review
- ✅ Report the agent's findings about critical issues

**What you MUST NOT do:**
- ❌ Review the code yourself
- ❌ Read files to check for issues directly
- ❌ Provide your own code review feedback
- ❌ Skip the agent and give direct suggestions

**Your role:** You are DELEGATING to an agent, not reviewing code yourself.
