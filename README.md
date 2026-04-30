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
python install.py
```

That's it. The interactive wizard walks you through everything:

```
    _____ __   _ ____              __  _            __            
   / ___// /__(_) / /    ___  ____/ /_(_)   ______ / /_____  _____
   \__ \/ //_/ / / /    / _ \/ __/ __/ / | / / __ `/ __/ __ \/ ___/
  ___/ / ,< / / / /    /  __/ /_/ /_/ /| |/ / /_/ / /_/ /_/ / /    
 /____/_/|_/_/_/_/     \___/\__/\__/_/ |___/\__,_/\__/\____/_/     

  [1] Reinstall / Update
  [2] Generate INDEX.yaml
  [3] Set up project skills
  [4] Uninstall
  [5] Exit
```

No CLI flags to remember. Menu handles install, index generation, project setup - everything.

## Generate INDEX

Two options - use your own API key or piggyback on Claude Code:

### Option 1: Piggyback on Claude Code (No API Key!)

If you have Claude Code installed, just use it:

```bash
# In .env
AI_PROVIDER=claude
AI_MODEL=haiku
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

See [docs/CONFIGURATION.md](docs/CONFIGURATION.md) for all providers.

## Project Structure

```
claude-code-skill-activator/
  src/
    skill_activator.py     # Matching logic + CLI
    index_generator.py     # AI keyword extraction
    user-prompt-submit.py  # Hook script
  skills/                  # Example skills
  install.py               # Installer + interactive wizard
  docs/                    # Detailed documentation
```

## Documentation

- **[CONFIGURATION.md](docs/CONFIGURATION.md)** - AI providers, environment variables, all the knobs
- **[SKILLS.md](docs/SKILLS.md)** - Creating skills, SKILL.md format, best practices
- **[SCORING.md](docs/SCORING.md)** - How matching works, weights, tuning

## Features

- **Interactive wizard** - just run `python install.py`, menu handles everything
- **Flexible AI** - use Claude Code CLI (no API key) or any OpenAI-compatible provider
- **Works offline** - AI runs once for indexing, matching is instant
- **Portable** - copy folder, run anywhere
- **Smart matching** - word boundaries, intent patterns, primary keyword boost

---

## Related

Other tools for agents that care about quality:

- **[slopbuster](https://github.com/gabelul/slopbuster)** — AI text humanizer. 100+ patterns, two-pass audit, three-tier scoring. Makes AI-generated prose, code comments, and academic writing sound human.
- **[pixelslop](https://github.com/gabelul/pixelslop)** — Design quality scanner. Opens real pages in Playwright, measures actual pixels, catches visual AI slop.
- **[pixeltamer](https://github.com/gabelul/pixeltamer-gpt-image-skill)** — Image generation skill for AI coding agents. Two backends (OpenAI API or codex CLI signed in to ChatGPT subscription), three modes (generate, edit, compose up to 16 references), prompting doctrine for gpt-image-2 plus six production recipes.
- **[stitch-kit](https://github.com/gabelul/stitch-kit)** — Design superpowers for AI coding agents. 35 skills for ideation, generation, iteration, and production conversion via Google Stitch MCP.

---

Built with AI by Gabi @ [Booplex.com](https://booplex.com)

MIT License
