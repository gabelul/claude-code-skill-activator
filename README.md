# Portable Skill Activator

Auto-detect and suggest Claude Code skills based on what you type. No AI at runtime - just fast keyword matching.

I built this because manually maintaining skill keywords was driving me nuts. The obvious solution: let AI extract keywords once, then never think about it again.

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

## Generate INDEX (No API Key Needed!)

If you have Claude Code installed, piggyback on it:

```bash
# In .env
AI_PROVIDER=claude
AI_MODEL=haiku
```

```bash
python src/index_generator.py ./skills
```

That's it. Uses your existing Claude Code auth.

Want OpenAI or another provider? See [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Project Structure

```
portable-skill-activator/
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

- **No API key required** - piggybacks on Claude Code CLI
- **Works offline** - AI runs once, matching is instant
- **Portable** - copy folder, run anywhere
- **Smart matching** - word boundaries, intent patterns, primary keyword boost

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