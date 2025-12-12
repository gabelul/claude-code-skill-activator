# Enhanced Skill Output Design

## Overview

Enhance the skill activation system to show multiple skill suggestions with enforcement levels and a configurable output format.

## Goals

1. **Better visibility** - Show multiple relevant skills, not just the best match
2. **Enforcement control** - Distinguish between required vs suggested vs optional skills
3. **User configurability** - Toggle between classic and enhanced output via installer

## Schema Changes

### INDEX.yaml - Add `enforcement` field

```yaml
skills:
  frontend-guidelines:
    keywords:
      english: [react, component, frontend]
    priority: high
    enforcement: required    # NEW: required | suggested | optional
    confidence_threshold: 0.7
    use_cases: [...]

  code-review:
    keywords:
      english: [review, code, pr]
    priority: medium
    enforcement: suggested   # NEW
    confidence_threshold: 0.6
```

**Defaults:**
- If `enforcement` not specified → defaults to `suggested`
- Backwards compatible with existing INDEX.yaml files

### Config file - `~/.claude/skill_config.json`

```json
{
  "output_format": "classic",
  "max_suggestions": 3
}
```

## Output Formats

### Classic Mode (current behavior)

Single skill, simple format:

```
<user-prompt-submit-hook>
SKILL AUTO-ACTIVATED

Based on your request, the following skill has been selected:

- **systematic-debugging** (confidence: 100%)
  A structured four-phase framework for investigating and fixing bugs

ACTION REQUIRED: Use the Skill tool to activate `systematic-debugging` before proceeding.

User request follows:
</user-prompt-submit-hook>
```

### Enhanced Mode

#### When a `required` skill matches (show alone)

```
<user-prompt-submit-hook>
⚠️ REQUIRED SKILL

You MUST activate this skill before proceeding:

  • frontend-guidelines (98% match)
    Enforce MUI v7 patterns and React best practices

ACTION: Use the Skill tool to activate `frontend-guidelines` BEFORE responding.

User request follows:
</user-prompt-submit-hook>
```

#### When no required skills, show up to 3 suggested/optional

```
<user-prompt-submit-hook>
SKILL SUGGESTIONS

Based on your request, these skills are relevant:

📚 SUGGESTED:
  • code-review (92% match)
    Review code for best practices and potential issues
  • testing-patterns (78% match)
    Patterns for writing effective tests

📌 OPTIONAL:
  • documentation (65% match)
    Generate documentation from code

ACTION: Consider using the Skill tool to activate relevant skills.

User request follows:
</user-prompt-submit-hook>
```

#### When only 1 suggested skill matches

```
<user-prompt-submit-hook>
SKILL SUGGESTION

📚 SUGGESTED:
  • systematic-debugging (100% match)
    Four-phase framework for investigating and fixing bugs

ACTION: Consider using the Skill tool to activate `systematic-debugging`.

User request follows:
</user-prompt-submit-hook>
```

## Installer Integration

### New menu option for existing installs

```
▸ What would you like to do?

  [1] Reinstall / Update
  [2] Generate INDEX.yaml
  [3] Set up project skills
  [4] Configure settings        ← NEW
  [5] Uninstall
  [6] Exit
```

### Configure settings screen

```
▸ Configure Settings

  ─────────────────────────────────────────

  OUTPUT FORMAT
  Controls how skill suggestions appear in chat

  [1] Classic (current)
      • Shows only the best matching skill
      • Simple, minimal output
      • Same message style for all skills

      Example:
      SKILL AUTO-ACTIVATED
      - **debugging** (confidence: 95%)
      ACTION REQUIRED: Use the Skill tool...

  [2] Enhanced
      • Shows up to 3 relevant skills
      • Groups by importance (required/suggested/optional)
      • Stronger language for critical skills

      Example:
      ⚠️ REQUIRED SKILL
      You MUST activate this skill before proceeding:
        • frontend-guidelines (98% match)

  Choose [1-2]: _

  ─────────────────────────────────────────

  MAX SUGGESTIONS (Enhanced mode only)
  How many skills to show when multiple match

  [1] 1 - Minimal, just the best match
  [2] 2 - Best match + one alternative
  [3] 3 - Up to three relevant skills (recommended)

  Choose [1-3]: _
```

### First-time install prompt

```
▸ Installation Complete!

  One more thing - choose your preferred output format:

  [1] Classic - Simple, shows 1 skill (recommended for beginners)
  [2] Enhanced - Rich, shows multiple skills with priorities

  Choose [1-2] [1]: _
```

## Behavior Logic

```python
def user_prompt_submit_hook(message):
    config = load_config()
    matches = detect_skills(message)

    if config["output_format"] == "classic":
        return format_classic_output(matches[0])

    # Enhanced mode
    required = [m for m in matches if m.enforcement == "required"]

    if required:
        # Show only the required skill, alone
        return format_required_output(required[0])

    # Group remaining by enforcement
    suggested = [m for m in matches if m.enforcement == "suggested"]
    optional = [m for m in matches if m.enforcement == "optional"]

    # Limit to max_suggestions total
    max_count = config["max_suggestions"]
    return format_enhanced_output(suggested, optional, max_count)
```

## Files to Modify

1. **`src/skill_activator.py`**
   - Add `load_config()` function
   - Add `format_classic_output()` function
   - Add `format_enhanced_output()` function
   - Add `format_required_output()` function
   - Modify `user_prompt_submit_hook()` to use config
   - Handle `enforcement` field in skill metadata

2. **`run.py`**
   - Add "Configure settings" menu option
   - Add `configure_settings()` function
   - Add `save_config()` / `load_config()` functions
   - Prompt for output format on first install

3. **`src/index_generator.py`** (or the AI prompt)
   - Update extraction prompt to include `enforcement` field

## Backwards Compatibility

- Existing INDEX.yaml files without `enforcement` → defaults to `suggested`
- Missing config file → defaults to `classic` mode
- No breaking changes to existing installations
