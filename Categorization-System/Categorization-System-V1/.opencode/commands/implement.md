---
description: Implement a feature or code change with full quality checks
---

Implement the following feature/change: $ARGUMENTS

## Workflow

### 1. Read Documentation First

**MUST FOLLOW documentation** — Read these files before implementing:

- `docs/conventions.md` — Naming patterns, file structure, standard practices
- `docs/formatting.md` — Code style, formatting rules, import organization
- `docs/system_patterns.md` — Architectural patterns, design decisions
- `docs/tech_context.md` — Technologies, constraints, dependencies

### 2. Implement the Feature

- Follow all documented patterns and conventions
- Use established naming conventions
- Respect architectural decisions
- Maintain consistency with existing code

### 3. Test the Implementation

After implementing, write comprehensive tests:

- Read `docs/testing.md` to understand test patterns
- Check for existing tests — extend them if possible
- Write unit tests (fast, isolated, FIRST principles)
- Write integration tests for critical workflows
- Run newly created tests to verify they pass
- Run ALL tests to ensure no regressions

### 4. Before Finishing

- Run linter and fix any errors
- Run formatters if documented in `docs/formatting.md`
- Verify all tests pass
- Check that code follows project conventions
- Ensure no debug code or comments left behind
