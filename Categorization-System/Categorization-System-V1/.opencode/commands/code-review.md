---
description: Review code changes for critical security, performance, and correctness issues
---

Review code changes for critical issues only.

Focus area (if specified): $ARGUMENTS

## 1. Get Changes

Use git read commands:
- `git status` - see modified files
- `git diff` - unstaged changes
- `git diff --staged` - staged changes
- `git diff main...HEAD` - all branch changes vs main
- `git log -p -n 5` - recent commits with diffs

## 2. Understand Documented Patterns

Read documentation to understand existing patterns:
- `docs/system_patterns.md` - Architectural patterns and design decisions
- `docs/conventions.md` - Naming conventions, file structure
- `docs/formatting.md` - Code style and formatting rules
- `docs/tech_context.md` - Technical constraints and dependencies

## 3. Review Against Standards

Identify if changes break established:
- Architectural patterns and design decisions
- Naming conventions and code formatting
- Module relationships and boundaries
- Technical constraints

## 4. Check for Critical Issues

Focus on **critical issues only**:

- **Bugs**: Logic errors, null handling, edge cases, off-by-one, race conditions
- **Performance**: N+1 queries, inefficient algorithms, memory leaks, unnecessary database hits, missing indexes
- **Security**: SQL injection, XSS, auth bypasses, authorization issues, data exposure, exposed secrets, missing input validation
- **Correctness**: Business logic errors, data integrity violations, state management issues, transaction handling
- **Pattern Breaks**: Violations of established architectural patterns, breaks module boundaries, introduces tech debt

## 5. Analyze Context

Don't just review the diff:
- Read surrounding code to understand context
- Check how changed code is called
- Verify error handling paths
- Understand data flow through the change
- Look for downstream impacts

## Output Format

**If critical issues found:**
```
ISSUES FOUND

- [Brief critical issue with file:line reference]
- [Another critical issue with specific details]
```

**If no critical issues:**
```
APPROVED

No critical issues. Ready to merge.
```

**Skip**: minor style issues, nitpicks, personal preferences, non-critical suggestions, micro-optimizations, formatting (handled by tools).

## Review Priorities

1. **Security vulnerabilities** - Highest priority
2. **Bugs that will cause failures** - High priority
3. **Performance issues** - Medium priority
4. **Pattern violations** - Medium priority
5. **Code quality concerns** - Low priority (only if critical)

When reporting issues, be specific: reference file and line numbers, explain the problem, describe the impact.
