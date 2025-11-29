# Portable Skill Activator

Keyword-based skill auto-detection for Claude Code. No AI at runtime, no embeddings, no slow queries. AI generates the index once, then everything runs on fast string matching.

I built this because manually maintaining skill keywords was driving me nuts, and I wanted my skills to work across different machines without reconfiguring everything each time. The obvious solution was to let AI do the tedious keyword extraction once, then never think about it again.

## What it actually does

1. Discovers skills from multiple locations (project, user, system, custom paths)
2. Uses AI to extract keywords, tags, use cases, and intent patterns from your `SKILL.md` files (one-time generation)
3. Matches user messages against keywords using weighted scoring with word boundary detection
4. Suggests relevant skills based on confidence threshold

The key insight: runtime AI for every message is slow and expensive. Generate the index once, match fast forever. I tested the "just use AI every time" approach - it works, but adds latency to every single message. This is better.

## Quick Start

### Option 1: Global Install (recommended)

Install once, works everywhere:

```bash
python install.py --user --hook --skills
```

This:
- Installs the skill activator to `~/.claude/`
- Sets up a hook that auto-suggests skills on every message
- Copies 4 example skills with pre-generated INDEX

Done. Every Claude Code session now has skill auto-detection.

### Option 2: Project-Level Only

Want skills just for one project? No global install needed:

```bash
# 1. Copy the skills folder to your project
cp -r skills/ /path/to/your/project/skills/

# 2. Set up AI config (for index generation)
cp .env.example .env
# Edit .env with your API key

# 3. Generate INDEX for your project skills
python skill_activator.py --generate-index /path/to/your/project/skills
```

If you have the global hook installed, it automatically checks project folders first. Project skills override global ones with the same name.

### Skill Discovery Order

The activator checks these locations (highest priority first):

| Priority | Location | Use Case |
|----------|----------|----------|
| 1 | `./skills/` | Project-specific skills |
| 2 | `./.claude/skills/` | Project-specific (alt) |
| 3 | `~/.claude/skills/` | User global skills |
| 4 | System path | Shared team skills |
| 5 | `CLAUDE_SKILLS_PATH` | Custom locations |

**Want to test without installing?**
```bash
python skill_activator.py --project . "I want to create generative art"
# Should match: algorithmic-art
```

**Or run the interactive wizard:**
```bash
python skill_activator.py
```

## Installation

```bash
python install.py
```

You'll see a menu:
- **[1] Global install** - Installs hook + activator to `~/.claude/`. Works for all projects.
- **[2] Set up project skills** - Asks for a project path. Detects existing skills and offers to generate INDEX.
- **[3] Both** - Global install + set up a project.
- **[4] Info** - Shows installation paths and exits.

CLI flags if you prefer:
```bash
python install.py --user --hook   # Global install (non-interactive)
python install.py --info          # Show paths
```

## Skill Discovery Order

Skills load from multiple locations. Higher priority wins if the same skill exists in multiple places.

| Priority | Location | Description |
|----------|----------|-------------|
| 1 | `./.claude/skills/` | Project-local |
| 2 | `./skills/` | Project-local alternative |
| 3 | `~/.claude/skills/` | User global (Windows: `%APPDATA%\claude\skills`) |
| 4 | System path | Platform-specific |
| 5 | `CLAUDE_SKILLS_PATH` | Custom paths from environment |

## Creating Skills

Each skill is a folder with a `SKILL.md` file:

```
~/.claude/skills/
  my-skill/
    SKILL.md      # Required - has the frontmatter and instructions
    README.md     # Optional - detailed docs
```

### SKILL.md Format

```markdown
---
name: my-skill
description: "What shows up in recommendations"
priority: high
keywords:
  english:
    - keyword1
    - keyword2
tags:
  - category1
use_cases:
  - "When someone needs X"
auto_activate: true
confidence_threshold: 0.7
---

# My Skill

Instructions for Claude go here. This is what gets loaded when the skill activates.
```

## AI-Powered Index Generation

Writing keywords manually gets old fast. Let AI handle it.

### Setup - The Easy Way (No API Key!)

If you already have Claude Code installed, you can piggyback on it. No API key needed:

```bash
# In .env
AI_PROVIDER=claude
AI_MODEL=haiku
```

That is it. The index generator spawns Claude CLI with Haiku (fast and cheap) to extract keywords. Works because you are already authenticated with Claude Code.

**Model options for claude provider:**
- `haiku` - Fast, cheap, good enough for keyword extraction (default)
- `sonnet` - Better quality if you want it
- `opus` - Overkill for this, but hey, your call

### Setup - Traditional API Key

1. Create `.env` from the example (or just edit `.env` directly):
```bash
AI_PROVIDER=openai
AI_API_KEY=your-key
AI_MODEL=gpt-4o-mini
```

2. Test the connection:
```bash
python skill_activator.py --test-ai
```

3. Generate the index:
```bash
python skill_activator.py --generate-index ./skills
```

That's it. The AI reads each `SKILL.md`, extracts keywords, tags, and use cases, then writes `INDEX.yaml`. Run it once when you add or update skills. Not per message.

### Supported Providers

Works with anything OpenAI-compatible:

| Provider | Setup | Notes |
|----------|-------|-------|
| Claude CLI | `AI_PROVIDER=claude` | **No API key needed!** Uses your Claude Code auth |
| OpenAI | `AI_PROVIDER=openai` | Works out of the box |
| Anthropic | `AI_PROVIDER=anthropic` | Native support |
| Ollama | `AI_PROVIDER=ollama` | Local, free |
| OpenRouter | `AI_PROVIDER=openrouter` | Access to many models |
| Custom | `AI_PROVIDER=custom` | Any OpenAI-compatible endpoint |

For custom endpoints, set `AI_BASE_URL` to your API endpoint. I've tested this with various proxy services and self-hosted setups - if it speaks OpenAI's API format, it'll work.

### Interactive Wizard

Running with no arguments gives you a menu:

```bash
python skill_activator.py
```

Options:
1. Test skill matching
2. List all skills
3. Show search paths
4. Generate INDEX.yaml (AI)
5. Test AI connection
6. Configure settings
7. Exit

The wizard walks you through AI configuration if you haven't set it up yet. Useful when you're getting started or testing on a new machine.

## Environment Configuration

All AI settings go in `.env`:

```bash
# Provider and model
AI_PROVIDER=openai
AI_API_KEY=your-key
AI_MODEL=gpt-4o-mini

# Optional: custom endpoint
AI_BASE_URL=https://your-api.com/v1

# Optional: fallback models if primary fails
AI_FALLBACK_MODELS=gpt-4o-mini,gpt-3.5-turbo

# Optional: rate limiting (helpful if you're hitting API limits)
AI_RATE_LIMIT_RPM=20
AI_MAX_RETRIES=3

# Languages for keyword extraction (default: english)
AI_LANGUAGES=english
```

## CLI Reference

```bash
# Match skills against a message
python skill_activator.py "your message here"

# List discovered skills
python skill_activator.py --list

# Show where skills are loaded from
python skill_activator.py --paths

# Generate INDEX.yaml using AI
python skill_activator.py --generate-index ./skills

# Test AI connection
python skill_activator.py --test-ai

# Debug mode - shows full request/response (useful when things break)
python skill_activator.py --test-ai --debug

# JSON output (for scripting)
python skill_activator.py --json "message"

# Specify project directory
python skill_activator.py --project /path/to/project "message"

# Override confidence threshold
python skill_activator.py --threshold 0.5 "message"
```

## Python API

```python
from skill_activator import SkillActivator

activator = SkillActivator(project_path="/your/project")

# Get skill matches
matches = activator.detect_skills("I need ROI analysis")
for skill, confidence in matches:
    print(f"{skill.name}: {confidence:.0%}")

# Get formatted suggestion text
suggestion = activator.process_message("I need ROI analysis")
```

## Scoring Algorithm

Keywords are matched with different weights:

| Match Type | Weight |
|------------|--------|
| Exact match | 3.0 |
| Compound match | 2.5 |
| Use case match | 2.5 |
| Partial match | 1.5 |
| Tag match | 2.0 |

Score is multiplied by priority (`high`: 1.5x, `medium`: 1.0x, `low`: 0.7x).

Skills only show if confidence exceeds their threshold (default 0.7). I found 0.7 works well for most cases - low enough to catch relevant skills, high enough to avoid noise.

## How the AI Index Works

```
SKILL.md files
     |
     v
[AI analyzes content]  <-- Run once when skills change
     |
     v
INDEX.yaml (keywords, tags, use_cases, intent_patterns)
     |
     v
[Fast keyword matching with word boundaries]  <-- Every message, no AI needed
```

The AI extracts simple, short keywords (1-2 words) that users would actually type. I spent way too long debugging why skills weren't matching before realizing the AI was generating phrases like "comprehensive financial analysis" when users just type "ROI" or "budget". The prompt now explicitly tells it to keep keywords simple.

## Custom Skill Paths

Add paths via environment variable:

**Windows:**
```powershell
$env:CLAUDE_SKILLS_PATH = "C:\MySkills;D:\TeamSkills"
```

**Linux/macOS:**
```bash
export CLAUDE_SKILLS_PATH="/path/to/skills:/another/path"
```

## Project Structure

```
portable-skill-activator/
  src/
    skill_activator.py     # Main script + CLI + wizard + matching logic
    index_generator.py     # AI index generation (supports claude CLI piggyback)
    user-prompt-submit.py  # Hook script for Claude Code
  skills/                  # Example skills with pre-generated INDEX
  install.py               # Installer
  .env.example             # AI config template
```

OLD_STRUCTURE
  src/
    skill_activator.py     # Main script + CLI + wizard + matching logic
    index_generator.py     # AI index generation (supports claude CLI piggyback)
    user-prompt-submit.py  # Hook script for Claude Code
  skills/                  # Example skills with pre-generated INDEX
  install.py               # Installer
  .env.example             # AI config template
```

## Uninstall

```bash
python install.py --uninstall
```

---

## That is It!

You now have a skill activation system that:

- **Works offline** - no AI needed at runtime, just fast keyword matching
- **No API key required** - piggybacks on Claude Code CLI for index generation
- **Travels with you** - copy the folder, run on any machine
- **Stays out of your way** - generates the index once, then forget about it
- **Actually matches what you type** - word boundaries, primary keywords, intent patterns
- **Smart scoring** - tags and use cases actually matter now (boosted weights)

Questions? Problems? Ideas? Open an issue. This exists because I got tired of manually maintaining keyword lists and wanted something that just works.

---

## Built by Booplex

Built with AI (and the stubborn refusal to maintain keyword lists manually) by Gabi @ [Booplex.com](https://booplex.com)

Part of the ongoing experiment to make AI tools that solve real problems instead of just looking impressive in demos.

**Booplex** - Where AI meets human creativity, and they actually get stuff done.

### Connect

- Website: [booplex.com](https://booplex.com)
- X: [@booplex](https://x.com/booplex)
- LinkedIn: [Connect with Gabi](https://linkedin.com/in/gabelul)
- Email: hey@booplex.com

P.S. - Yes, AI helped build this. That's kind of the whole point.

---

## License

MIT
