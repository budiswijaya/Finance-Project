# Project Instructions

## Documentation-First Workflow

**ALWAYS read the existing documentation in the `docs/` folder before starting any work.** This ensures you understand the system architecture, technical context, and existing patterns.

Use `@docs-guide` agent when you need a structured summary of project documentation relevant to the current task.

## Project Documentation Structure

This project maintains comprehensive documentation in the `docs/` folder:

1. `docs/system_patterns.md` - System architecture, key technical decisions, design patterns, component relationships
2. `docs/tech_context.md` - Technologies used, development setup, technical constraints, dependencies
3. `docs/testing.md` - Test types and structure, fixtures and mocking guidance, how to run tests
4. `docs/formatting.md` - Language version, formatting rules and conventions, indentation and line length standards
5. `docs/conventions.md` - Standard app structure, naming conventions, pagination patterns, startup and signal registration

## Agent Workflow

1. **Before any task**: Read relevant documentation from `docs/` folder
2. **When documentation needs updating**: Use `@docs-writer` agent to update appropriate doc files
3. **Follow documented patterns**: All work must align with established conventions and architectural decisions

## Documentation Update Guidelines

- Add to existing docs when the update fits the file's context and purpose
- Keep module/system structure - organize by components, not chronologically
- Only add important changes - document architectural decisions, patterns, and technical constraints
- Keep docs concise and scannable - use bullet points and headers
- Document WHY decisions were made, not just what was done

## Documentation Standards

### When to Update Existing Docs

- **Add to existing files** when the update fits the file's context and purpose
- **Keep module/system structure** - organize content by system components, not chronologically
- **Only add important changes** - document architectural decisions, patterns, and technical constraints

### When to Create New Docs

- **Create new files** when documenting a new independent system or major feature
- **Use descriptive names** that clearly indicate the content (e.g., `payment_integration.md`, `caching_strategy.md`)

### Documentation Quality

- Keep docs **concise and scannable** - use bullet points and headers
- Document **why** decisions were made, not just what was done
- Maintain **logical structure** within files - group related concepts together
