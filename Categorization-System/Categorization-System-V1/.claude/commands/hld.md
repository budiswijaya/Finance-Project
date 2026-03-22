---
description: Create a high-level design document through guided Q&A
allowed-tools: Read, Write, Glob, AskUserQuestion, Bash
argument-hint: [feature-name]
---

Create a High-Level Design (HLD) document for: **$ARGUMENTS**

## Your Role

You are an HLD facilitator. Your job is to:
1. Gather information through conversation context and targeted questions
2. Track completion of all 15 HLD sections
3. Generate ASCII art diagrams for architecture and data flow
4. Only write the final HLD when the user confirms readiness

**DO NOT** write the HLD immediately. First gather all required information.

---

## MANDATORY Workflow

### Step 1: Check for Existing HLD

First, check if `/docs/hlds/$ARGUMENTS.md` already exists:
- If it exists: Warn the user and STOP. This command only creates new HLDs.
- If it doesn't exist: Continue to Step 2.

### Step 2: Scan Conversation Context

Review the current conversation for any existing information about:
- Problem being solved
- System components mentioned
- Technologies discussed
- Requirements stated

Extract and note any relevant context already available.

### Step 3: Present HLD Checklist

Present the 15-section HLD checklist showing what information is needed:

```
HLD Sections Status for: $ARGUMENTS
─────────────────────────────────────
[ ] 1.  Problem Statement
[ ] 2.  Goals
[ ] 3.  Non-Goals
[ ] 4.  Architecture Overview
[ ] 5.  Components
[ ] 6.  Data Flow
[ ] 7.  Technology Choices
[ ] 8.  Integration Points
[ ] 9.  Security Considerations
[ ] 10. Scalability & Performance
[ ] 11. Risks & Mitigations
[ ] 12. Deployment Architecture
[ ] 13. Observability
[ ] 14. Open Questions
[ ] 15. References
```

Mark any sections that can be filled from conversation context.

### Step 4: Gather Information Through Phases

Ask questions in logical phases. Use AskUserQuestion for structured choices when appropriate.

**Phase 1: Context & Problem**
- What problem does this solve?
- Who are the stakeholders/users?
- Why is this needed now?

**Phase 2: Scope**
- What are the main goals? (2-4 bullet points)
- What is explicitly OUT of scope?

**Phase 3: Technical Design**
- What are the main components/modules?
- How do they interact with each other?
- What technologies/frameworks will be used and why?

**Phase 4: Integration & Data**
- What external systems does this integrate with?
- How does data flow through the system?
- What are the main data entities?

**Phase 5: Quality Attributes**
- What are the security requirements?
- What are performance/scalability expectations?
- Any compliance requirements?

**Phase 6: Deployment & Operations**
- How will this be deployed? (environments, CI/CD)
- What infrastructure is needed?
- How will you monitor and log?

**Phase 7: Risks & Open Items**
- What could go wrong? What are the mitigations?
- What decisions are still unresolved?
- Any relevant references or prior art?

### Step 5: Track Progress

After each user response:
1. Update your internal tracking of which sections are complete
2. Show updated checklist with [x] for completed, [~] for partial/TBD, [ ] for missing
3. Ask about the next incomplete section

The user can say:
- "N/A" - Mark section as not applicable
- "TBD" - Mark section as to be determined (will use placeholder)
- "skip" - Skip to next section
- "done" - Ready to generate the HLD

### Step 6: Generate ASCII Diagrams

When you have enough information, generate ASCII art diagrams for:

**Architecture Overview** - Show system boundaries and component relationships:
```
┌─────────────────────────────────────────────────────────────┐
│                      System Name                             │
├─────────────────────────────────────────────────────────────┤
│    ┌──────────┐      ┌──────────┐      ┌──────────┐        │
│    │Component │─────▶│Component │─────▶│Component │        │
│    │    A     │      │    B     │      │    C     │        │
│    └──────────┘      └──────────┘      └──────────┘        │
└─────────────────────────────────────────────────────────────┘
```

**Data Flow** - Show request/response patterns:
```
┌────────┐    Request    ┌────────┐    Query     ┌────────┐
│ Source │──────────────▶│Process │─────────────▶│ Store  │
└────────┘               └────────┘              └────────┘
```

**Deployment** - Show infrastructure layout:
```
┌─────────────────────────────────────────────────────────────┐
│                     Environment                              │
│  ┌─────────┐    ┌─────────┐    ┌─────────┐                  │
│  │ Service │───▶│ Service │───▶│ Service │                  │
│  └─────────┘    └─────────┘    └─────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

### Step 7: Present Summary

Before writing, show a summary:

```
HLD Ready for: $ARGUMENTS
─────────────────────────────────────
[x] 1.  Problem Statement     - Complete
[x] 2.  Goals                 - Complete
[~] 3.  Non-Goals             - TBD
[x] 4.  Architecture Overview - Complete (with diagram)
...
─────────────────────────────────────
Sections: 12 complete, 2 TBD, 1 N/A
```

Ask user to confirm: "Ready to write the HLD to `/docs/hlds/$ARGUMENTS.md`?"

### Step 8: Write the HLD

Only after user confirmation:

1. Ensure `/docs/hlds/` directory exists (create if needed)
2. Write the HLD using the template below
3. Report success with the file path

---

## HLD Template

```markdown
# High-Level Design: {Feature Name}

**Author:** {author or TBD}
**Date:** {current date}
**Status:** Draft

## 1. Problem Statement
{problem description and why it matters}

## 2. Goals
- {goal 1}
- {goal 2}

## 3. Non-Goals
- {explicitly out of scope items}

## 4. Architecture Overview
{high-level description}

{ASCII diagram here}

## 5. Components
### 5.1 {Component Name}
- **Responsibility:** {what it does}
- **Interfaces:** {how it connects}

## 6. Data Flow
{description}

{ASCII diagram here}

## 7. Technology Choices
| Technology | Purpose | Rationale |
|------------|---------|-----------|
| {tech} | {use} | {why chosen} |

## 8. Integration Points
- {external system}: {how it integrates}

## 9. Security Considerations
- {security items}

## 10. Scalability & Performance
- {considerations}

## 11. Risks & Mitigations
| Risk | Impact | Mitigation |
|------|--------|------------|
| {risk} | {impact} | {mitigation} |

## 12. Deployment Architecture
- **Environments:** {environments}
- **Infrastructure:** {infrastructure}
- **CI/CD:** {deployment approach}

{ASCII diagram here if applicable}

## 13. Observability
- **Logging:** {approach}
- **Metrics:** {what to measure}
- **Alerting:** {conditions}

## 14. Open Questions
- [ ] {unresolved question}

## 15. References
- {related docs, links}
```

---

## Important Rules

- **DO NOT** skip the information gathering phase
- **DO NOT** write the HLD until user confirms
- **DO** use ASCII art diagrams for visual sections
- **DO** allow flexible completion (TBD placeholders are OK)
- **DO** track and display progress after each interaction
- **DO** extract any relevant context from the conversation history
