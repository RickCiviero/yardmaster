# Pricing table

Data as of **2026-11-23**, from `skills/yardmaster/pricing.json`. **Verified: no.**

> Prices and credit multipliers are ESTIMATES (4.5-generation list prices and relative ratios). Verify every row against the vendor pricing pages and set verified=true before a release (docs/wiki/Pricing.md).

Yardmaster uses these numbers only to estimate spend and savings. It never changes a price on its own, and it lists a model with no price as *unpriced* rather than guessing. Source URLs for each vendor's pricing page are **not recorded yet**; add them here when each row is verified.

## vscode-copilot

Unit: Copilot credits (a multiplier per request).

| Model | Tier | Multiplier |
|---|---|---|
| `gpt-6-luna` | light | 0.25 |
| `haiku` | light | 0.33 |
| `sonnet` | standard | 1.0 |
| `gpt-5` | standard | 1.0 |
| `opus` | heavy | 3.0 |
| `fable` | frontier | 10.0 |

## copilot-cli

Unit: Copilot credits (a multiplier per request).

| Model | Tier | Multiplier |
|---|---|---|
| `gpt-6-luna` | light | 0.25 |
| `haiku` | light | 0.33 |
| `sonnet` | standard | 1.0 |
| `gpt-5` | standard | 1.0 |
| `opus` | heavy | 3.0 |
| `fable` | frontier | 10.0 |

## claude-code

Unit: USD per million tokens.

| Model | Tier | Input | Output | Cached input |
|---|---|---|---|---|
| `haiku` | light | 1.0 | 5.0 | 0.1 |
| `sonnet` | standard | 3.0 | 15.0 | 0.3 |
| `opus` | heavy | 5.0 | 25.0 | 0.5 |
| `claude-fable-5-1` | frontier | 15.0 | 75.0 | 1.5 |

## codex

Unit: USD per million tokens.

| Model | Tier | Input | Output | Cached input |
|---|---|---|---|---|
| `gpt-5-mini` | light | 0.25 | 2.0 | 0.025 |
| `gpt-5-codex` | standard | 1.25 | 10.0 | 0.125 |
| `gpt-5` | heavy | 1.25 | 10.0 | 0.125 |
| `gpt-5-pro` | frontier | 15.0 | 120.0 | 1.5 |

## Tiers

`light` lookups and small edits, `standard` routine coding, `heavy` multi-step implementation and hard debugging, `frontier` architecture and deep research.
