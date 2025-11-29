# Claude Code Skill Activator

Auto-detect and suggest Claude Code skills based on what you type. AI extracts keywords once, then fast string matching handles runtime - no latency, works offline.

I built this because manually maintaining skill keywords was driving me nuts. The obvious solution: let AI do the tedious extraction once, then never think about it again.

## How It Works

1. AI analyzes your `SKILL.md` files once, extracts keywords → writes `INDEX.yaml`
2. Hook watches every message you type
3. Fast string matching suggests relevant skills
4. You approve, Claude loads the skill

No runtime AI. No latency. Just works.

## Quick Start

```bash
python install.py --user --hook --skills
```

Done. Every Claude Code session now has skill auto-detection.

**Test it:**
```bash
python src/skill_activator.py "I need to debug this error"
# Should match: systematic-debugging
```

## Generate INDEX

Two options - use your own API key or piggyback on Claude Code:

### Option 1: Piggyback on Claude Code (No API Key!)

If you have Claude Code installed, just use it:

```bash
# In .env
AI_PROVIDER=claude
AI_MODEL=haiku
```

```bash
python src/index_generator.py ./skills
```

Uses your existing Claude Code auth. Zero extra setup.

### Option 2: Your Own API Key

Works with OpenAI, Anthropic, Ollama, OpenRouter, or any OpenAI-compatible endpoint:

```bash
# In .env
AI_PROVIDER=openai
AI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini
```

```bash
python src/index_generator.py ./skills
```

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all providers.

## Project Structure

```
claude-code-skill-activator/
  src/
    skill_activator.py     # Matching logic + CLI
    index_generator.py     # AI keyword extraction
    user-prompt-submit.py  # Hook script
  skills/                  # Example skills
  install.py               # Installer
  docs/                    # Detailed documentation
```

## Documentation

- **[CONFIGURATION.md](docs/CONFIGURATION.md)** - AI providers, environment variables, all the knobs
- **[SKILLS.md](docs/SKILLS.md)** - Creating skills, SKILL.md format, best practices
- **[SCORING.md](docs/SCORING.md)** - How matching works, weights, tuning

## Features

- **Flexible AI** - use Claude Code CLI (no API key) or any OpenAI-compatible provider
- **Works offline** - AI runs once for indexing, matching is instant
- **Portable** - copy folder, run anywhere
- **Smart matching** - word boundaries, intent patterns, primary keyword boost

---

Built with AI by Gabi @ [Booplex.com](https://booplex.com)

MIT License
