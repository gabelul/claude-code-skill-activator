# Scoring Algorithm

How the skill activator decides which skills to suggest.

## The Basics

Every skill gets a score based on how well the user's message matches its keywords, tags, and use cases. Higher score = better match.

Score must exceed the skill's `confidence_threshold` (default 0.7) to be suggested.

## Match Types and Weights

| Match Type | Weight | What It Means |
|------------|--------|---------------|
| Exact match | 3.0 | Keyword found with word boundaries |
| Use case match | 2.5 | Matches a use_case description |
| Compound match | 2.5 | Multi-word keyword matches |
| Tag match | 2.0 | Matches a category tag |
| Partial match | 1.5 | Substring/prefix match |

## Word Boundary Detection

We match whole words, not substrings. This prevents false positives:

- "debug" matches "I need to debug this" ✓
- "debug" does NOT match "debugger" or "debugging" ✗

Uses regex `\bkeyword\b` pattern under the hood.

## Primary Keyword Boost

The first 3 keywords of each skill are "primary" and get 2x extra weight.

Why? If "debug" is the first keyword for `systematic-debugging`, it should match stronger than skills where "debug" is just mentioned somewhere in a use case.

## Intent Patterns

The AI can extract regex patterns like:
- `debug.*(issue|error|bug)`
- `test.*(coverage|unit|integration)`
- `refactor.*(code|function|class)`

These catch complex intents even when words aren't adjacent:
- "I need to debug this weird error" → matches `debug.*(issue|error|bug)`

## Priority Multiplier

After calculating the base score, it's multiplied by priority:

| Priority | Multiplier |
|----------|------------|
| high | 1.5x |
| medium | 1.0x |
| low | 0.7x |

## Example Calculation

User types: "help me debug this error"

**systematic-debugging skill:**
- "debug" exact match: 3.0
- "debug" is primary keyword (first 3): +6.0 (3.0 × 2.0)
- "error" exact match: 3.0
- Intent pattern `debug.*(error)` matches: +2.5
- Priority high: ×1.5
- **Total: (3.0 + 6.0 + 3.0 + 2.5) × 1.5 = 21.75**

**when-stuck skill:**
- "debug" partial match in use case: 1.5
- Priority medium: ×1.0
- **Total: 1.5 × 1.0 = 1.5**

systematic-debugging wins by a landslide.

## Tuning Tips

**Skill matches too often (false positives):**
- Raise `confidence_threshold` to 0.8 or higher
- Make keywords more specific
- Lower the priority

**Skill never matches (false negatives):**
- Lower `confidence_threshold` to 0.5-0.6
- Add more keywords (or regenerate INDEX)
- Check that keywords are simple 1-2 word terms
- Raise the priority

**Multiple skills competing:**
- Use priority to rank them
- Make keywords more distinct
- Consider merging similar skills

## Debugging Matches

```bash
# See what matches and why
python src/skill_activator.py "your test message"

# JSON output with scores
python src/skill_activator.py --json "your test message"
```

## The INDEX.yaml File

This is where all the searchable data lives:

```yaml
skills:
  my-skill:
    keywords:
      english:
        - keyword1
        - keyword2
    tags:
      - category1
    use_cases:
      - "When you need X"
    intent_patterns:
      - "keyword1.*(related|terms)"
```

Regenerate it after editing skills:

```bash
python src/index_generator.py ./skills
```
