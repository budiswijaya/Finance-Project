---
description: Explore and understand codebase architecture, patterns, and design decisions
---

Explore and understand the codebase for the specified subject.

Focus area: $ARGUMENTS

## Role: Exploration Only

**DO NOT**: Debug issues, plan features, propose fixes, generate implementation tasks

**DO**: Explore patterns, map relationships, understand architecture, document data flows, identify conventions

## Workflow

### 1. Read Documentation First

Read docs/ folder to understand existing documented patterns:
- `docs/system_patterns.md` - Architectural patterns and design decisions
- `docs/conventions.md` - Naming conventions, file structure
- `docs/tech_context.md` - Technologies, constraints, dependencies
- `docs/formatting.md` - Code style and formatting rules

### 2. Explore the Codebase

Examine:
- File structure and organization
- Component relationships and dependencies
- Design patterns in use
- Naming conventions and coding standards
- Data flows and architectural decisions

### 3. Analyze and Synthesize

Identify high-level patterns, design principles, trade-offs, and common abstractions.

## Output Format

### Architecture & Design
- High-level patterns used
- Design principles evident in the code

### Component Relationships
- How modules/classes interact
- Key dependencies and data flows

### Conventions & Patterns
- Coding patterns consistently used
- Naming conventions
- Common abstractions

### Notable Decisions
- Interesting architectural choices
- Trade-offs that were made
- Framework/library usage patterns

## Update Documentation (If Needed)

If you discovered significant undocumented patterns or architectural decisions:
- Identify the correct docs/ file to update
- Add to existing sections (don't duplicate)
- Keep concise, document **why** decisions were made
- Only add important architectural decisions and patterns
