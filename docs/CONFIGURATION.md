# Configuration

All the knobs for AI providers, models, and environment settings.

## AI Providers

### Claude CLI (Recommended - No API Key!)

If you have Claude Code installed, just use it:

```bash
AI_PROVIDER=claude
AI_MODEL=haiku
```

The index generator spawns `claude --model haiku` under the hood. You're already authenticated, so no extra setup.

**Models:**
- `haiku` - Fast, cheap, perfect for keyword extraction (default)
- `sonnet` - Better quality if you want it
- `opus` - Overkill but hey, your call

### OpenAI

```bash
AI_PROVIDER=openai
AI_API_KEY=sk-...
AI_MODEL=gpt-4o-mini
```

### Anthropic (Direct)

```bash
AI_PROVIDER=anthropic
AI_API_KEY=sk-ant-...
AI_MODEL=claude-3-haiku-20240307
```

### Ollama (Local)

```bash
AI_PROVIDER=ollama
AI_MODEL=llama3.2
AI_BASE_URL=http://localhost:11434/v1
```

Free, local, no API key. Just need Ollama running.

### OpenRouter

```bash
AI_PROVIDER=openrouter
AI_API_KEY=sk-or-...
AI_MODEL=anthropic/claude-3-haiku
```

Access to tons of models through one API.

### Custom Endpoint

```bash
AI_PROVIDER=custom
AI_API_KEY=your-key
AI_BASE_URL=https://your-api.com/v1
AI_MODEL=whatever-model
```

Works with anything OpenAI-compatible.

## Full Environment Reference

```bash
# =============================================================================
# REQUIRED: Pick one provider
# =============================================================================
AI_PROVIDER=claude           # claude, openai, anthropic, ollama, openrouter, custom

# =============================================================================
# PROVIDER-SPECIFIC
# =============================================================================
AI_API_KEY=your-key          # Not needed for claude provider
AI_MODEL=haiku               # Model name (provider-specific)
AI_BASE_URL=                 # Custom endpoint URL (optional)

# =============================================================================
# OPTIONAL: Tuning
# =============================================================================
AI_FALLBACK_MODELS=gpt-4o-mini,gpt-3.5-turbo   # Try these if primary fails
AI_RATE_LIMIT_RPM=20                            # Requests per minute limit
AI_MAX_RETRIES=3                                # Retry failed requests
AI_TIMEOUT=60                                   # Request timeout in seconds
AI_LANGUAGES=english                            # Keyword extraction languages

# =============================================================================
# SKILL PATHS
# =============================================================================
CLAUDE_SKILLS_PATH=/custom/path:/another/path   # Additional skill directories
```

## Custom Skill Paths

By default, skills are discovered from:

1. `./skills/` - Project-specific
2. `./.claude/skills/` - Project-specific (alt)
3. `~/.claude/skills/` - User global
4. System paths - Platform-specific

Add custom paths via environment:

**Windows:**
```powershell
$env:CLAUDE_SKILLS_PATH = "C:\MySkills;D:\TeamSkills"
```

**Linux/macOS:**
```bash
export CLAUDE_SKILLS_PATH="/path/to/skills:/another/path"
```

## Testing Your Setup

```bash
# Test AI connection
python src/skill_activator.py --test-ai

# Debug mode (shows full request/response)
python src/skill_activator.py --test-ai --debug

# Generate index for a skills folder
python src/index_generator.py ./skills
```

## Troubleshooting

**"Claude CLI not found"**
- Make sure Claude Code is installed and `claude` is in your PATH
- Try running `claude --version` to verify

**"API key invalid"**
- Double-check your key in `.env`
- Make sure there are no extra spaces or quotes

**"Model not found"**
- Check the model name for your provider
- OpenRouter models need the full path like `anthropic/claude-3-haiku`

**"Rate limited"**
- Set `AI_RATE_LIMIT_RPM` to a lower value
- Or just wait a bit and retry
