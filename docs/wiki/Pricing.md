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

## Verification attempt (2026-11-24)

Result: **not verified**. `pricing.json` keeps `verified: false`. Do not use the savings estimates for decisions yet.

| Source | What it shows | Effect on this table |
|---|---|---|
| Anthropic pricing pages (docs.claude.com, anthropic.com) | Could not be reached from the build environment (DNS failure) | The Claude Code rows are unconfirmed |
| OpenAI API pricing (openai.com/api) | Per million input / output tokens: GPT-6.2 Astra $8.00 / $40.00, GPT-6.2 Sol $2.00 / $10.00, GPT-6.1 Terra $1.00 / $5.00, GPT-6 Luna $0.10 / $0.50 (standard rates, context under 272K). No cached-input prices | The `codex` rows (`gpt-5`, `gpt-5-mini`, `gpt-5-codex`, `gpt-5-pro`) were not found on the pages read, so they are unconfirmed and may be out of date. The current Codex docs use GPT-6.1 Sol in their example |
| GitHub Copilot billing (per-token rates, not provider list prices) | Per million input / output tokens: Claude Haiku 5.5 $0.10 / $0.50 (up to 100K context), Sonnet 5.5 $2.00 / $10.00, Opus 5.5 $4.00 / $20.00, Fable 5.1 $10.00 / $50.00, GPT-6 Luna $0.10 / $0.50 | A different unit from the credit multipliers used for the Copilot rows, so it cannot confirm them |
| GitHub legacy premium-request page | Multipliers for annual Pro and Pro+ plans on older models (Haiku 4.5 0.33, Sonnet 4.6 9, Opus 4.8 27). The page says GitHub moved to usage-based billing on June 1, 2026 | The Copilot multipliers (`opus` 3.0, `fable` 10.0, and the rest) are not confirmed |

Open decision for the owner: which model ids the Codex and Copilot writers should use (the GPT-6 family or the gpt-5
family), and whether Copilot routing should use credit multipliers or per-token rates.
