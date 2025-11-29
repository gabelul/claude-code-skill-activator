# Creating Skills

How to build skills that the activator can detect and suggest.

## Skill Structure

Each skill is a folder with at least a `SKILL.md` file:

```
my-skill/
  SKILL.md      # Required - frontmatter + instructions
  README.md     # Optional - detailed docs
  examples/     # Optional - whatever else you need
```

## SKILL.md Format

```markdown
---
name: my-skill
description: "Short description shown in suggestions"
priority: high
keywords:
  english:
    - keyword1
    - keyword2
tags:
  - category1
  - category2
use_cases:
  - "When you need to do X"
  - "When facing Y problem"
auto_activate: true
confidence_threshold: 0.7
---

# My Skill

Everything below the frontmatter is the actual skill content.
This is what Claude loads when the skill activates.

Write your instructions, guidelines, templates - whatever
helps Claude do the task.
```

## Frontmatter Fields

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique skill identifier |
| `description` | Yes | Shows in suggestions (keep it short) |
| `priority` | No | `high`, `medium`, `low` (affects scoring) |
| `keywords` | No | Manual keywords (AI generates these if missing) |
| `tags` | No | Categories for grouping |
| `use_cases` | No | "When to use this" descriptions |
| `auto_activate` | No | Allow auto-suggestion (default: true) |
| `confidence_threshold` | No | Min score to suggest (default: 0.7) |

## AI-Generated vs Manual Keywords

**Let AI do it (recommended):**
1. Write your SKILL.md with just the basics
2. Run `python src/index_generator.py ./skills`
3. AI extracts keywords, tags, use_cases, intent patterns
4. Everything goes in `INDEX.yaml`

**Manual keywords:**
- Add them directly in frontmatter under `keywords.english`
- AI will still enrich them during index generation
- Useful for domain-specific terms AI might miss

## Writing Good Skills

### Keep Instructions Clear
Claude will follow exactly what you write. Be specific about:
- What the skill does
- When to use it vs other approaches
- Step-by-step process if there is one
- Examples of good output

### Keywords That Actually Match

The AI extracts simple 1-2 word terms users actually type. But you can help:

**Good keywords:**
- `debug`, `error`, `fix`, `bug`
- `test`, `unit test`, `coverage`
- `refactor`, `clean up`, `optimize`

**Bad keywords (too specific):**
- `comprehensive debugging methodology`
- `systematic error analysis framework`

### Priority Levels

- `high` (1.5x) - Core skills you use constantly
- `medium` (1.0x) - Regular use
- `low` (0.7x) - Niche or experimental

### Confidence Threshold

Default 0.7 works for most skills. Adjust if:
- Too many false positives → raise to 0.8+
- Missing obvious matches → lower to 0.5-0.6
- Very specific skill → raise to 0.85+

## Skill Discovery Order

Higher priority wins if same skill exists in multiple places:

1. `./skills/` - Project-specific
2. `./.claude/skills/` - Project-specific (alt)
3. `~/.claude/skills/` - User global
4. System path - Platform-specific
5. `CLAUDE_SKILLS_PATH` - Custom paths

## Example Skill

```markdown
---
name: code-review
description: "Review code for bugs, security, and best practices"
priority: high
tags:
  - quality
  - review
use_cases:
  - "When you want feedback on code"
  - "Before merging a PR"
  - "When something feels off but you can't pinpoint it"
---

# Code Review

Review code systematically for:

1. **Bugs** - Logic errors, edge cases, null checks
2. **Security** - Injection, auth issues, data exposure
3. **Performance** - Unnecessary loops, N+1 queries, memory leaks
4. **Maintainability** - Naming, structure, complexity

## Process

1. Read the full context first
2. Check each category above
3. Prioritize issues by severity
4. Suggest specific fixes, not just problems

## Output Format

For each issue found:
- **Location:** file:line
- **Severity:** critical/high/medium/low
- **Issue:** What's wrong
- **Fix:** How to fix it
```

## Regenerating INDEX

After editing skills, regenerate the index:

```bash
python src/index_generator.py ./skills
```

The INDEX.yaml file contains all extracted keywords, tags, use_cases, and intent patterns. This is what the activator actually searches.
