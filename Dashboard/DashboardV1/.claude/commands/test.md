---
description: Write comprehensive tests for code/features using the tester agent
allowed-tools: Agent
---

🚨 CRITICAL: You MUST delegate this work to the tester agent. DO NOT write tests yourself.

Write comprehensive tests for the specified code or feature.

Test target: $ARGUMENTS

## MANDATORY Workflow

**STEP 1: Invoke the tester agent**

Use the Task tool to delegate to the tester agent:
```
Task(subagent_type='tester', prompt='Write comprehensive tests for: $ARGUMENTS')
```

**What you MUST do:**
- ✅ Use the Task tool with subagent_type='tester'
- ✅ Pass the test target description to the agent
- ✅ Wait for the agent to write the tests
- ✅ Report what tests the agent created

**What you MUST NOT do:**
- ❌ Write test code yourself
- ❌ Create or edit test files directly
- ❌ Skip the agent and implement tests on your own
- ❌ Provide test code examples instead of using the agent

**Your role:** You are DELEGATING to an agent, not writing tests yourself.
