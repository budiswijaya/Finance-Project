---
description: Implement a feature or code change with tests and quality checks
---

Implement the following feature/change: $ARGUMENTS

## Phase 1: Read Documentation First

**MUST read** these documentation files before implementing:

- `docs/conventions.md` - Naming patterns, file structure, standard practices
- `docs/formatting.md` - Code style, formatting rules, import organization
- `docs/system_patterns.md` - Architectural patterns, design decisions
- `docs/tech_context.md` - Technologies, constraints, dependencies
- `docs/testing.md` - Testing requirements and patterns

## Phase 2: Implement the Feature

- Follow all documented patterns and conventions
- Use established naming conventions
- Respect architectural decisions
- Maintain consistency with existing code
- Don't invent new patterns when existing ones work
- Use existing utilities and abstractions
- Respect module boundaries and dependencies

### Code Quality Standards

- **Readability**: Code is simple and clear
- **Naming**: Functions and variables are well-named
- **DRY**: No duplicated code
- **Error Handling**: Proper error handling and validation
- **Security**: No exposed secrets, proper input validation

## Phase 3: Write & Run Tests

1. **Read `docs/testing.md`** to understand project test patterns
2. **Check existing tests** - extend them if possible, only create new if needed
3. **Write comprehensive tests**:
   - **Unit Tests**: Test in isolation, must be instant, mock external deps, follow FIRST principles
   - **Integration Tests**: Test workflows, mock only external services
   - **Coverage**: Happy path, error cases, edge cases, permissions, side effects
4. **Run newly created tests** to verify they pass
5. **Run ALL tests** to ensure no regressions
6. **Never skip or delete** failing tests

## Phase 4: Quality Checks

- Run linter and fix any errors
- Run formatters if documented in `docs/formatting.md`
- Self-review for critical issues (bugs, security, performance, pattern violations)
- Ensure no debug code or comments left behind
- Confirm proper error handling
