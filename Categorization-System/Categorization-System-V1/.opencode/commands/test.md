---
description: Write comprehensive tests for code/features
---

Write comprehensive tests for the specified code/feature/bug fix.

Test target: $ARGUMENTS

## Workflow

1. **Read `docs/testing.md`** to understand how to write and execute tests
2. Check for existing tests for the subject — if possible, extend them to cover new use cases. Only create new test files if none exist or extending doesn't make sense.
3. **Run tests** to verify they pass

## Testing Pyramid

Follow the testing pyramid approach — focus on unit tests at the base, with fewer integration tests at the top:

**Unit Tests (Foundation)**:

- Test single function/method/component in isolation
- Must be instant — fast feedback loop
- Mock all external dependencies (databases, APIs, file systems, services)
- **Follow FIRST Principles**:
  - **Fast**: Tests run in milliseconds
  - **Independent**: No dependencies between tests, can run in any order
  - **Repeatable**: Same result every time, no flaky tests
  - **Self-Validating**: Clear pass/fail, no manual inspection needed
  - **Timely**: Written alongside or before implementation code

**Integration Tests (Top Layer)**:

- Test how components work together, full workflows
- Slower, more expensive to run
- Mock only external services (3rd party APIs, external systems)
- Cover critical user journeys, main business flows

Refer to `docs/testing.md` for project-specific patterns:

- Test framework and runner configuration
- Fixtures and setup patterns
- Mocking approaches for the tech stack
- How to run tests in the project

## After Writing Tests

1. Run newly created tests to verify they pass
2. Check test execution time (unit tests must be instant)
3. If tests fail, fix the code or the test UNTIL THEY PASS
4. Run ALL tests for ALL apps and verify they pass too, never skip/delete/remove failing tests even if they are not related to changes made.
