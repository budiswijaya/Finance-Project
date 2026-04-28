---
description: Write comprehensive tests for code, features, or bug fixes
---

Write comprehensive tests for the specified code or feature.

Test target: $ARGUMENTS

## Workflow

1. **Read `docs/testing.md`** to understand test patterns, fixtures, and how to run tests
2. **Check existing tests** for the subject - extend them if possible. Only create new test files if none exist or extending doesn't make sense.
3. **Write comprehensive tests** following project patterns

## Testing Pyramid

### Unit Tests (Foundation)

- Test single function/method/component in isolation
- Must be instant - fast feedback loop
- Mock all external dependencies (databases, APIs, file systems, services)
- **FIRST Principles**: Fast, Independent, Repeatable, Self-Validating, Timely

### Integration Tests (Top Layer)

- Test how components work together, full workflows
- Mock only external services (3rd party APIs, external systems)
- Cover critical user journeys, main business flows

## Test Coverage Checklist

- Happy path (valid inputs, expected behavior)
- Error cases (invalid inputs, constraints)
- Edge cases (null values, empty lists, boundaries)
- Permissions (different user roles if applicable)
- Side effects (database state, async tasks)

## After Writing Tests

1. Run newly created tests to verify they pass
2. Check test execution time (unit tests must be instant)
3. If tests fail, fix the code or test until they pass
4. Run ALL tests for ALL apps and verify they pass too
5. Never skip/delete/remove failing tests even if they are not related to changes made
