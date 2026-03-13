---
description: Implement a feature or code change using the implementer agent
allowed-tools: Agent
---

🚨 CRITICAL: You MUST delegate ALL work to agents. DO NOT write ANY code yourself.

Implement the following feature/change with full quality checks:

$ARGUMENTS

## MANDATORY Workflow

You MUST follow these steps in order. Each step REQUIRES using the Task tool with the specified agent.

---

**MANDATORY STEP 1: Invoke the implementer agent**

Use the Task tool to delegate implementation to the implementer agent:
```
Task(subagent_type='implementer', prompt='Implement the following following project standards: $ARGUMENTS')
```

**What you MUST do in Step 1:**
- ✅ Use the Task tool with subagent_type='implementer'
- ✅ Pass the complete feature/change description to the agent
- ✅ Wait for the agent to complete the implementation
- ✅ Verify the agent wrote the code

**What you MUST NOT do in Step 1:**
- ❌ Write ANY implementation code yourself
- ❌ Edit ANY files directly
- ❌ Create ANY new files yourself
- ❌ Skip the agent and do the work yourself
- ❌ "Help" the agent by writing code

---

**MANDATORY STEP 2: Invoke the tester agent**

After implementation is complete, use the Task tool to delegate test writing to the tester agent:
```
Task(subagent_type='tester', prompt='Write comprehensive tests for the implementation completed in the previous step')
```

**What you MUST do in Step 2:**
- ✅ Use the Task tool with subagent_type='tester'
- ✅ Wait for the agent to write comprehensive tests
- ✅ Verify the agent created test files

**What you MUST NOT do in Step 2:**
- ❌ Write ANY test code yourself
- ❌ Create or edit test files directly
- ❌ Skip the agent and write tests yourself
- ❌ Provide test examples instead of using the agent

---

**MANDATORY STEP 3: Invoke the code-reviewer agent**

After tests are written, use the Task tool to delegate code review to the code-reviewer agent:
```
Task(subagent_type='code-reviewer', prompt='Review all changes from the implementation and testing steps for critical issues')
```

**What you MUST do in Step 3:**
- ✅ Use the Task tool with subagent_type='code-reviewer'
- ✅ Wait for the agent to complete its review
- ✅ Report any critical issues the agent found

**What you MUST NOT do in Step 3:**
- ❌ Review the code yourself
- ❌ Provide your own code review feedback
- ❌ Skip the agent and give direct suggestions
- ❌ Read files to check for issues yourself

---

**MANDATORY STEP 4: Report completion**

After all agents complete their work:
- ✅ Summarize what the implementer agent built
- ✅ Summarize what tests the tester agent created
- ✅ Report any issues found by the code-reviewer agent

**Your role:** You are the ORCHESTRATOR who delegates to agents. You are NOT the implementer, tester, or reviewer.
