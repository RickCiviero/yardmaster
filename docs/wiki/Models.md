# Models

Yardmaster routes by **strength**, not by price. The catalog says which models each harness offers and how strong each
one is. It holds no prices, so routing never depends on what a model costs.

For every chat the question is: how strong was the model that did the work, and could a weaker model have done it?
`/yardmaster ledger` reports the tokens each harness and model used, split by strength, so you can weigh the savings
yourself.

## Strength tiers

| Tier | Meaning |
|---|---|
| light | lookups, small edits, simple questions |
| standard | routine coding, tests, clear bug fixes |
| heavy | multi-step implementation, cross-file refactors, hard debugging |
| frontier | architecture, planning difficult work, deep research |

Within a tier, the first model listed is the weakest and is chosen first. If a tier has no allowed model, the next tier
up is used, never a lower one.

## Models by harness

### claude-code

| Model | Tier | Also called |
|---|---|---|
| `haiku` | light | `claude-haiku-5-5` |
| `sonnet` | standard | `claude-sonnet-5-5` |
| `opus` | heavy | `claude-opus-5-5` |
| `fable` | frontier | `claude-fable-5-1` |

### vscode-copilot

| Model | Tier | Also called |
|---|---|---|
| `gpt-6-luna` | light | - |
| `haiku` | light | `claude-haiku-5-5` |
| `sonnet` | standard | `claude-sonnet-5-5` |
| `opus` | heavy | `claude-opus-5-5` |
| `fable` | frontier | - |

### copilot-cli

| Model | Tier | Also called |
|---|---|---|
| `gpt-6-luna` | light | - |
| `haiku` | light | `claude-haiku-5-5` |
| `sonnet` | standard | `claude-sonnet-5-5` |
| `opus` | heavy | `claude-opus-5-5` |
| `fable` | frontier | - |

### codex

| Model | Tier | Also called |
|---|---|---|
| `gpt-6-luna` | light | - |
| `gpt-6.1-terra` | standard | - |
| `gpt-6.2-sol` | heavy | - |
| `gpt-6.2-astra` | frontier | - |

## Not confirmed yet

- The tier placement of every model is Yardmaster's assumption, from each family's place in its line-up.
- The GPT-6 names for Codex, and for GPT-6 in Copilot, are not yet confirmed in a live install. Check them in your own
  model picker before you rely on them. `/yardmaster doctor` says so.
- The families were taken from the OpenAI API model list and GitHub's Copilot model list, checked on 2026-11-24.

Older prices and their verification notes were removed in this version: the code does not need them.

See also: [How it works](How-it-works).
