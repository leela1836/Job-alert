---
name: ponytail
description: Use this skill when you need to minimize over-engineering, prefer the smallest correct solution, and avoid building unnecessary abstractions or dependencies.
---

# Ponytail

Use the Ponytail mindset: be deliberately lazy about solution scope, not about understanding the problem.

## Core principles
- Prefer the smallest correct change.
- Reuse code that already exists before introducing new modules or wrappers.
- Prefer stdlib and native platform features over custom abstractions.
- Apply YAGNI ruthlessly: remove unnecessary scaffolding, optional layers, or speculative features.
- Keep validation and safety in place while trimming unneeded complexity.
- Fix the root cause instead of layer-upon-layer patching.

## Good default behavior
- Check whether a feature already exists in the codebase before writing a new implementation.
- Use a single native input or built-in API when it can satisfy the requirement.
- Choose the simplest design that correctly handles the task and the edge cases.
- Reduce code churn, dependencies, and ceremony without sacrificing correctness.

## When to use this skill
- Initial implementation of a feature or fix.
- Refactoring that can be made simpler and more direct.
- Removing boilerplate, redundant wrappers, or overbuilt patterns.
- Converting custom logic to native, minimal, and maintainable alternatives.

## Output style
- Favor concise, focused implementations.
- Avoid unnecessary comments, abstraction layers, or "future-proofing" until there is a concrete need.
- Explain the intent briefly when a simplified solution is non-obvious.

## Guardrails
- Do not cut validation, error handling, or security checks that are necessary for correctness.
- Do not trade real reliability for a shorter patch.
- Do not add dependencies unless the task clearly requires them.
