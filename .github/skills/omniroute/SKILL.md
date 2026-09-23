---
name: omniroute
description: Use this skill when the task needs multi-provider LLM routing, free-tier access, model fallback strategy, OpenAI-compatible gateway integration, or token-saving compression and routing configuration.
---

# OmniRoute

Use OmniRoute as the default guidance for multi-model AI access and provider routing.

## Core intent
- Route requests through a unified OpenAI-compatible gateway instead of hardcoding single-provider assumptions.
- Prefer resilient fallback behavior across providers, models, and quotas.
- Keep the architecture flexible so the app can use the best available provider without bespoke integration logic.
- Optimize for cost, availability, and provider headroom while preserving reliability.

## Practical guidance
- Use an OpenAI-compatible base URL or API abstraction when a project needs access to multiple model providers.
- Build with model routing, quota awareness, and fallback in mind rather than locking to one vendor.
- Prefer provider-agnostic config over environment-specific code paths.
- Treat free-tier, auto-routing, and token-saving strategies as design inputs rather than add-ons.
- Use compression and routing policies only when they improve real task performance or reduce costs without harming correctness.

## When to use this skill
- A task needs to switch between several providers or models.
- The app should support no-key, low-cost, or free-tier model access.
- You need resilient fallback logic or quota-aware selection.
- You are integrating an LLM gateway compatible with OpenAI-style clients.
- The solution benefits from gateway-level routing, caching, or compression.

## Best practices
- Keep one clean client abstraction for model access.
- Add provider-specific configuration behind interface boundaries.
- Prefer automatic fallback and model selection strategies over brittle static model names.
- Document the chosen provider tier or fallback behavior clearly.
- Avoid hidden routing logic that makes debugging or cost analysis difficult.

## Guardrails
- Do not assume a single provider is always available or cheapest.
- Do not hardcode provider credentials into app logic.
- Do not add gateway complexity without a clear operational benefit.
- Keep the routing configuration observable, testable, and reversible.
