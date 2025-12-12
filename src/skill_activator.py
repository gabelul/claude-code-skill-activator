#!/usr/bin/env python3
"""
Portable Skill Auto-Activator
Multi-source skill discovery and activation system

Features:
- System-wide, user, and project-local skill directories
- Auto-discovery from SKILL.md frontmatter (no manual INDEX.yaml needed)
- Environment variable configuration (CLAUDE_SKILLS_PATH)
- Merged index with priority handling

Usage:
  1. As CLI: python skill_activator.py "your message here"
  2. As Hook: Place in .claude/hooks/ or import SkillActivator
  3. As Module: from skill_activator import SkillActivator
"""

import os
import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field

# Try to import yaml, fall back to basic parser if not available
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# =============================================================================
# User Configuration (for output format toggle)
# =============================================================================

DEFAULT_USER_CONFIG = {
    "output_format": "classic",  # "classic" or "enhanced"
    "max_suggestions": 3,        # 1-5, how many skills to show in enhanced mode
}


def get_config_path() -> Path:
    """Get path to user config file"""
    return Path.home() / '.claude' / 'skill_config.json'


def load_user_config() -> dict:
    """Load user configuration from ~/.claude/skill_config.json"""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                user_config = json.load(f)
                # Merge with defaults to ensure all keys exist
                return {**DEFAULT_USER_CONFIG, **user_config}
        except (json.JSONDecodeError, IOError):
            pass
    return DEFAULT_USER_CONFIG.copy()


def save_user_config(config: dict) -> bool:
    """Save user configuration to ~/.claude/skill_config.json"""
    config_path = get_config_path()
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=2)
        return True
    except IOError:
        return False


@dataclass
class SkillMetadata:
    """Skill metadata container"""
    name: str
    path: Path
    source: str  # 'system', 'user', 'project', 'custom'
    priority: str = "medium"
    enforcement: str = "suggested"  # required | suggested | optional
    description: str = ""
    keywords_korean: List[str] = field(default_factory=list)
    keywords_english: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    use_cases: List[str] = field(default_factory=list)
    intent_patterns: List[str] = field(default_factory=list)  # Regex patterns for complex intents
    auto_activate: bool = True
    confidence_threshold: float = 0.5


class SkillActivator:
    """
    Multi-source keyword-based skill activation system

    Searches for skills in multiple locations with priority:
    1. Project-local: ./.claude/skills/ or ./skills/
    2. User global: ~/.claude/skills/
    3. System-wide: Platform-specific system directory
    4. Custom paths: CLAUDE_SKILLS_PATH environment variable
    """

    # Default configuration
    DEFAULT_CONFIG = {
        "mode": "suggest",  # suggest | auto
        "confidence_threshold": 0.5,  # Lower default for better recall
        "max_suggestions": 3,
        "priority_multipliers": {
            "high": 1.5,
            "medium": 1.0,
            "low": 0.7
        },
        "keyword_weights": {
            "exact_match": 3.0,      # Explicit keywords - highest priority
            "compound_match": 2.5,   # Multiple keywords in one skill keyword
            "partial_match": 1.5,    # Substring/prefix matches
            "tag_match": 2.0,        # Tags - boosted (categories help matching)
            "use_case_match": 2.5    # Use cases - boosted (describes WHEN to use)
        }
    }

    # Stopwords for keyword extraction
    STOPWORDS = {
        # Korean
        '해줘', '좀', '이거', '저거', '그거', '뭐', '뭔가', '어떻게', '왜', '언제',
        '어디', '누구', '무엇', '어떤', '있어', '없어', '하는', '되는', '같은',
        '있는', '없는', '해서', '해요', '합니다', '이다', '입니다', '새로운',
        '하려고', '있는데', '싶어', '만들어줘', '짜줘', '너무', '복잡한',
        '복잡해서', '찾고', '하고', '싶은', '필요',
        # English
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should',
        'could', 'can', 'may', 'might', 'must', 'shall', 'this', 'that', 'these',
        'those', 'i', 'you', 'he', 'she', 'it', 'we', 'they', 'me', 'him', 'her',
        'us', 'them', 'my', 'your', 'his', 'its', 'our', 'their', 'what', 'which',
        'who', 'when', 'where', 'why', 'how', 'please', 'just', 'some', 'need',
        'want', 'help', 'with', 'for', 'about', 'like', 'make', 'create', 'new',
        'to', 'of', 'in', 'on', 'at', 'by', 'from', 'or', 'and', 'as', 'so',
        'if', 'then', 'than', 'but', 'also', 'only', 'not', 'no', 'yes', 'all',
        'any', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'such'
    }

    KOREAN_PARTICLES = ['가', '이', '은', '는', '을', '를', '에', '에서', '에게',
                        '께서', '으로', '로', '의', '도', '만', '부터', '까지', '와', '과']

    def __init__(self,
                 project_path: Optional[str] = None,
                 config: Optional[Dict] = None,
                 skip_system: bool = False,
                 skip_user: bool = False,
                 override_threshold: Optional[float] = None):
        """
        Initialize SkillActivator

        Args:
            project_path: Project root directory (default: current working directory)
            config: Override default configuration
            skip_system: Skip system-wide skills
            skip_user: Skip user global skills
            override_threshold: Force this threshold for all skills (ignores per-skill thresholds)
        """
        self.project_path = Path(project_path) if project_path else Path.cwd()
        self.config = {**self.DEFAULT_CONFIG, **(config or {})}
        self.skip_system = skip_system
        self.skip_user = skip_user
        self.override_threshold = override_threshold

        # Discover all skill directories
        self.skill_paths = self._discover_skill_paths()

        # Load all skills
        self.skills: Dict[str, SkillMetadata] = {}
        self._load_all_skills()

    def _get_system_skill_path(self) -> Optional[Path]:
        """Get platform-specific system skill directory"""
        if sys.platform == 'win32':
            # Windows: %PROGRAMDATA%\claude\skills
            program_data = os.environ.get('PROGRAMDATA', 'C:\\ProgramData')
            return Path(program_data) / 'claude' / 'skills'
        elif sys.platform == 'darwin':
            # macOS: /Library/Application Support/claude/skills
            return Path('/Library/Application Support/claude/skills')
        else:
            # Linux: /usr/share/claude/skills
            return Path('/usr/share/claude/skills')

    def _get_user_skill_path(self) -> Path:
        """Get user-specific skill directory - ~/.claude/skills/ on all platforms"""
        # Claude Code uses ~/.claude/skills/ for personal skills on all platforms
        return Path.home() / '.claude' / 'skills'

    def _discover_skill_paths(self) -> List[Tuple[Path, str]]:
        """
        Discover all skill directories with their source type

        Returns:
            List of (path, source_type) tuples, ordered by priority (highest first)
        """
        paths = []

        # 1. Project-local skills (highest priority)
        project_paths = [
            self.project_path / '.claude' / 'skills',
            self.project_path / 'skills',
        ]
        for p in project_paths:
            if p.exists() and p.is_dir():
                paths.append((p, 'project'))

        # 2. User global skills
        if not self.skip_user:
            user_path = self._get_user_skill_path()
            if user_path.exists() and user_path.is_dir():
                paths.append((user_path, 'user'))

        # 3. System-wide skills
        if not self.skip_system:
            system_path = self._get_system_skill_path()
            if system_path and system_path.exists() and system_path.is_dir():
                paths.append((system_path, 'system'))

        # 4. Custom paths from environment variable
        custom_paths = os.environ.get('CLAUDE_SKILLS_PATH', '')
        if custom_paths:
            separator = ';' if sys.platform == 'win32' else ':'
            for custom_path in custom_paths.split(separator):
                custom_path = custom_path.strip()
                if custom_path:
                    p = Path(custom_path)
                    if p.exists() and p.is_dir():
                        paths.append((p, 'custom'))

        return paths

    def _parse_yaml_frontmatter(self, content: str) -> Optional[Dict]:
        """Parse YAML frontmatter from markdown content"""
        # Match YAML frontmatter between --- markers
        match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not match:
            return None

        yaml_content = match.group(1)

        if HAS_YAML:
            try:
                return yaml.safe_load(yaml_content)
            except yaml.YAMLError:
                return None
        else:
            # Basic YAML parser fallback
            return self._basic_yaml_parse(yaml_content)

    def _basic_yaml_parse(self, content: str) -> Dict:
        """Basic YAML parser for simple key-value pairs"""
        result = {}
        current_key = None
        current_list = None

        for line in content.split('\n'):
            line = line.rstrip()
            if not line or line.startswith('#'):
                continue

            # Check for list item
            if line.strip().startswith('- '):
                if current_list is not None:
                    item = line.strip()[2:].strip().strip('"\'')
                    current_list.append(item)
                continue

            # Check for key-value pair
            if ':' in line:
                indent = len(line) - len(line.lstrip())
                key_value = line.split(':', 1)
                key = key_value[0].strip()
                value = key_value[1].strip() if len(key_value) > 1 else ''

                if indent == 0:
                    current_key = key
                    if value:
                        # Remove quotes
                        value = value.strip('"\'')
                        # Handle booleans
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        # Handle numbers
                        elif value.replace('.', '').isdigit():
                            value = float(value) if '.' in value else int(value)
                        result[key] = value
                        current_list = None
                    else:
                        result[key] = {}
                        current_list = None
                elif current_key:
                    if value:
                        value = value.strip('"\'')
                        if value.lower() == 'true':
                            value = True
                        elif value.lower() == 'false':
                            value = False
                        if isinstance(result[current_key], dict):
                            result[current_key][key] = value
                        current_list = None
                    else:
                        # Start of a list
                        if isinstance(result[current_key], dict):
                            result[current_key][key] = []
                            current_list = result[current_key][key]
                        else:
                            result[current_key] = []
                            current_list = result[current_key]

        return result

    def _load_skill_from_directory(self, skill_dir: Path, source: str) -> Optional[SkillMetadata]:
        """Load skill metadata from a skill directory"""
        skill_md = skill_dir / 'SKILL.md'

        if not skill_md.exists():
            return None

        try:
            content = skill_md.read_text(encoding='utf-8')
        except Exception:
            return None

        frontmatter = self._parse_yaml_frontmatter(content)
        if not frontmatter:
            # No frontmatter, create basic metadata from directory name
            return SkillMetadata(
                name=skill_dir.name,
                path=skill_dir,
                source=source,
                description=f"Skill from {skill_dir.name}"
            )

        # Extract keywords
        keywords = frontmatter.get('keywords', {})
        if isinstance(keywords, dict):
            keywords_korean = keywords.get('korean', [])
            keywords_english = keywords.get('english', [])
        elif isinstance(keywords, list):
            # Flat list of keywords
            keywords_korean = []
            keywords_english = keywords
        else:
            keywords_korean = []
            keywords_english = []

        return SkillMetadata(
            name=frontmatter.get('name', skill_dir.name),
            path=skill_dir,
            source=source,
            priority=frontmatter.get('priority', 'medium'),
            enforcement=frontmatter.get('enforcement', 'suggested'),
            description=frontmatter.get('description', ''),
            keywords_korean=keywords_korean if isinstance(keywords_korean, list) else [],
            keywords_english=keywords_english if isinstance(keywords_english, list) else [],
            tags=frontmatter.get('tags', []) if isinstance(frontmatter.get('tags'), list) else [],
            use_cases=frontmatter.get('use_cases', []) if isinstance(frontmatter.get('use_cases'), list) else [],
            auto_activate=frontmatter.get('auto_activate', True),
            confidence_threshold=float(frontmatter.get('confidence_threshold', 0.5))
        )

    def _load_index_yaml(self, index_path: Path, source: str) -> Dict[str, SkillMetadata]:
        """Load skills from INDEX.yaml file"""
        skills = {}

        if not index_path.exists():
            return skills

        try:
            content = index_path.read_text(encoding='utf-8')
            if HAS_YAML:
                data = yaml.safe_load(content)
            else:
                # Skip INDEX.yaml if no yaml module
                return skills
        except Exception:
            return skills

        if not data or 'skills' not in data:
            return skills

        skills_dir = index_path.parent

        for skill_name, skill_data in data.get('skills', {}).items():
            if not isinstance(skill_data, dict):
                continue

            skill_path = skills_dir / skill_name
            keywords = skill_data.get('keywords', {})

            skills[skill_name] = SkillMetadata(
                name=skill_name,
                path=skill_path if skill_path.exists() else skills_dir,
                source=source,
                priority=skill_data.get('priority', 'medium'),
                enforcement=skill_data.get('enforcement', 'suggested'),
                description=skill_data.get('description', ''),
                keywords_korean=keywords.get('korean', []) if isinstance(keywords, dict) else [],
                keywords_english=keywords.get('english', []) if isinstance(keywords, dict) else [],
                tags=skill_data.get('tags', []),
                use_cases=skill_data.get('use_cases', []),
                intent_patterns=skill_data.get('intent_patterns', []),  # Regex patterns
                auto_activate=skill_data.get('auto_activate', True),
                confidence_threshold=float(skill_data.get('confidence_threshold', 0.5))
            )

        return skills

    def _load_all_skills(self):
        """Load all skills from discovered paths"""
        # Process in reverse order so higher priority overwrites lower
        for skill_path, source in reversed(self.skill_paths):
            # First, scan for skill directories with SKILL.md
            # (so INDEX.yaml can override/enhance them)
            if skill_path.is_dir():
                for item in skill_path.iterdir():
                    if item.is_dir():
                        skill = self._load_skill_from_directory(item, source)
                        if skill:
                            self.skills[skill.name] = skill

            # Then, load INDEX.yaml which can add keywords to existing skills
            # or define new skills without SKILL.md
            index_yaml = skill_path / 'INDEX.yaml'
            if index_yaml.exists():
                indexed_skills = self._load_index_yaml(index_yaml, source)
                # Merge INDEX.yaml data with existing skills
                for skill_name, indexed_skill in indexed_skills.items():
                    if skill_name in self.skills:
                        # Merge: INDEX.yaml enhances SKILL.md data
                        existing = self.skills[skill_name]
                        # Use INDEX.yaml keywords if SKILL.md has none
                        if not existing.keywords_korean and indexed_skill.keywords_korean:
                            existing.keywords_korean = indexed_skill.keywords_korean
                        if not existing.keywords_english and indexed_skill.keywords_english:
                            existing.keywords_english = indexed_skill.keywords_english
                        if not existing.tags and indexed_skill.tags:
                            existing.tags = indexed_skill.tags
                        if not existing.use_cases and indexed_skill.use_cases:
                            existing.use_cases = indexed_skill.use_cases
                        # INDEX.yaml priority/threshold override SKILL.md defaults
                        if indexed_skill.priority != 'medium':
                            existing.priority = indexed_skill.priority
                        if indexed_skill.confidence_threshold != 0.5:
                            existing.confidence_threshold = indexed_skill.confidence_threshold
                        if not indexed_skill.auto_activate:
                            existing.auto_activate = False
                    else:
                        # New skill from INDEX.yaml only
                        self.skills[skill_name] = indexed_skill

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from user message"""
        # Normalize text
        normalized = re.sub(r'[^\w\sㄱ-ㅎㅏ-ㅣ가-힣]', ' ', text.lower())

        words = []
        for w in normalized.split():
            w = w.strip()
            if len(w) < 2:
                continue

            # Remove Korean particles
            word_clean = w
            for particle in self.KOREAN_PARTICLES:
                if w.endswith(particle) and len(w) > len(particle) + 1:
                    word_clean = w[:-len(particle)]
                    break

            if word_clean and word_clean not in self.STOPWORDS:
                words.append(word_clean)

        return words

    def _check_word_boundary(self, keyword: str, text: str) -> bool:
        """Check if keyword exists in text with word boundaries (like claude-code-kit)"""
        try:
            # Escape special regex characters in keyword
            escaped = re.escape(keyword.lower())
            # Use word boundary matching
            pattern = rf'\b{escaped}\b'
            return bool(re.search(pattern, text.lower()))
        except re.error:
            # Fallback to simple contains if regex fails
            return keyword.lower() in text.lower()

    def _check_intent_patterns(self, patterns: List[str], text: str) -> bool:
        """Check if any intent pattern matches the text (like claude-code-kit)"""
        for pattern in patterns:
            try:
                if re.search(pattern, text, re.IGNORECASE):
                    return True
            except re.error:
                continue  # Skip invalid patterns
        return False

    def _calculate_match_score(self, user_keywords: List[str], skill: SkillMetadata,
                               original_message: str = "") -> float:
        """Calculate keyword matching score for a skill"""
        if not user_keywords:
            return 0.0

        score = 0.0
        weights = self.config['keyword_weights']

        # Check intent patterns FIRST - high priority match (like claude-code-kit)
        if skill.intent_patterns and original_message:
            if self._check_intent_patterns(skill.intent_patterns, original_message):
                # Intent pattern match is a strong signal - add significant score
                score += weights['exact_match'] * 2  # Double the weight for intent match

        # Combine all skill keywords
        skill_keywords = [k.lower() for k in skill.keywords_korean + skill.keywords_english]

        # Check for PRIMARY keywords with word boundaries (skill's first 3 keywords get extra weight)
        # This ensures "debug ai usage" matches skills where debug is a PRIMARY keyword
        if original_message and skill_keywords:
            message_lower = original_message.lower()
            primary_keywords = skill_keywords[:3]  # First 3 keywords are considered primary
            for pk in primary_keywords:
                if self._check_word_boundary(pk, message_lower):
                    score += weights['exact_match'] * 2.0  # Strong boost for primary keyword match
        skill_tags = [t.lower() for t in skill.tags]
        skill_use_cases = [u.lower() for u in skill.use_cases]

        # Extract keywords from use_cases for better matching
        use_case_keywords = set()
        stopwords = {'the', 'and', 'for', 'this', 'that', 'with', 'from', 'use', 'when',
                    'should', 'will', 'can', 'are', 'was', 'were', 'been', 'have', 'has',
                    'had', 'not', 'but', 'what', 'all', 'your', 'you', 'they', 'them',
                    'their', 'which', 'who', 'whom', 'how', 'any', 'some', 'such', 'more',
                    'most', 'other', 'into', 'over', 'only', 'than', 'then', 'also', 'just',
                    'about', 'using', 'before', 'after', 'during', 'like', 'need', 'needs'}
        for uc in skill.use_cases:
            words = re.findall(r'\b[a-zA-Z]{3,}\b', uc.lower())
            for w in words:
                if w not in stopwords:
                    use_case_keywords.add(w)

        # Extract keywords from description
        desc_keywords = set()
        if skill.description:
            desc_words = re.findall(r'\b[a-zA-Z]{3,}\b', skill.description.lower())
            for w in desc_words:
                if w not in stopwords:
                    desc_keywords.add(w)

        # Also extract keywords from description if no explicit keywords
        if not skill_keywords and desc_keywords:
            skill_keywords = list(desc_keywords)

        max_possible_score = len(user_keywords) * weights['exact_match']
        if max_possible_score == 0:
            return 0.0

        # Compound match detection
        matched_user_keywords = set()
        for skill_kw in skill_keywords:
            matching_parts = [uk for uk in user_keywords if uk in skill_kw and len(uk) >= 2]
            if len(matching_parts) >= 2:
                for uk in matching_parts:
                    matched_user_keywords.add(uk)
                score += len(matching_parts) * weights['compound_match']

        # Individual keyword matching with priority order
        for user_kw in user_keywords:
            if user_kw in matched_user_keywords:
                continue

            # 1. Exact match in explicit keywords (highest priority)
            if user_kw in skill_keywords:
                score += weights['exact_match']
                matched_user_keywords.add(user_kw)
            # 2. Match in use_case keywords (high priority - indicates when to use)
            elif user_kw in use_case_keywords:
                score += weights['use_case_match']
                matched_user_keywords.add(user_kw)
            # 3. Match in description keywords
            elif user_kw in desc_keywords:
                score += weights['partial_match']
                matched_user_keywords.add(user_kw)
            # 4. Partial match in explicit keywords (substring or prefix match)
            elif any(
                     # Substring match (e.g., "error" in "errors")
                     ((user_kw in sk or sk in user_kw) and
                      min(len(user_kw), len(sk)) >= 4 and
                      abs(len(user_kw) - len(sk)) <= 3) or
                     # Prefix/stemming match (e.g., "validate" -> "validation")
                     (len(user_kw) >= 5 and len(sk) >= 5 and
                      (sk.startswith(user_kw[:5]) or user_kw.startswith(sk[:5])))
                     for sk in skill_keywords):
                score += weights['partial_match']
                matched_user_keywords.add(user_kw)
            # 5. Tag match
            elif user_kw in skill_tags:
                score += weights['tag_match']
                matched_user_keywords.add(user_kw)

        # Bonus: Check if user message matches a use case pattern
        # (multiple user keywords appearing in the same use_case = strong signal)
        user_kw_set = set(user_keywords)
        for uc in skill_use_cases:
            uc_words = set(re.findall(r'\b[a-zA-Z]{3,}\b', uc))
            overlap = user_kw_set & uc_words
            if len(overlap) >= 2:
                # Multiple keywords match this use case - strong relevance signal
                score += len(overlap) * 0.5  # Bonus per overlapping word

        # Bonus: Check if user keywords match use_case_keywords with stemming
        # e.g., "debug" matches "debugging", "debugger"
        for user_kw in user_keywords:
            for uc_kw in use_case_keywords:
                # Check if one is prefix of the other (simple stemming)
                if (len(user_kw) >= 4 and len(uc_kw) >= 4 and
                    (uc_kw.startswith(user_kw) or user_kw.startswith(uc_kw))):
                    # Give bonus - this use_case talks about what user wants
                    score += 1.0  # Increased from 0.8 - use_cases are strong signal

        # Normalize and apply priority
        # Don't cap at 1.0 here - allows stemming bonuses to differentiate between skills
        # The display functions will cap the shown percentage at 100%
        normalized_score = score / max_possible_score
        multiplier = self.config['priority_multipliers'].get(skill.priority, 1.0)

        return normalized_score * multiplier

    def detect_skills(self, user_message: str) -> List[Tuple[SkillMetadata, float]]:
        """Detect relevant skills from user message"""
        user_keywords = self._extract_keywords(user_message)

        if not user_keywords:
            return []

        matches = []
        global_threshold = self.config['confidence_threshold']

        for skill in self.skills.values():
            if not skill.auto_activate:
                continue

            # Pass original message for intent pattern matching
            score = self._calculate_match_score(user_keywords, skill, user_message)

            # Use override if set, otherwise skill-specific, otherwise global
            if self.override_threshold is not None:
                threshold = self.override_threshold
            else:
                threshold = skill.confidence_threshold or global_threshold

            if score >= threshold:
                matches.append((skill, score))

        # Sort by score descending
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches[:self.config['max_suggestions']]

    def format_suggestion(self, matches: List[Tuple[SkillMetadata, float]],
                         language: str = 'en') -> str:
        """Format skill suggestions for display"""
        if not matches:
            return ""

        mode = self.config['mode']

        if mode == "auto":
            skill, score = matches[0]
            display_score = min(score, 1.0)  # Cap at 100% for display
            if language == 'ko':
                return f"""
🔄 **스킬 자동 활성화**
  - 스킬: {skill.name}
  - 출처: {skill.source}
  - 신뢰도: {display_score:.0%}
  - 설명: {skill.description}
"""
            else:
                return f"""
🔄 **Skill Auto-Activated**
  - Skill: {skill.name}
  - Source: {skill.source}
  - Confidence: {display_score:.0%}
  - Description: {skill.description}
"""
        else:
            if language == 'ko':
                lines = ["", "🎯 **관련 스킬 추천:**", ""]
                for i, (skill, score) in enumerate(matches, 1):
                    display_score = min(score, 1.0)  # Cap at 100% for display
                    lines.append(f"{i}. **{skill.name}** [{skill.source}] (신뢰도: {display_score:.0%})")
                    lines.append(f"   {skill.description}")
                    lines.append("")
                lines.append("💡 스킬 사용: `/skill {skill-name}` 또는 `@{path}/SKILL.md`")
            else:
                lines = ["", "🎯 **Recommended Skills:**", ""]
                for i, (skill, score) in enumerate(matches, 1):
                    display_score = min(score, 1.0)  # Cap at 100% for display
                    lines.append(f"{i}. **{skill.name}** [{skill.source}] (confidence: {display_score:.0%})")
                    lines.append(f"   {skill.description}")
                    lines.append("")
                lines.append("💡 To use: `/skill {skill-name}` or `@{path}/SKILL.md`")

            return "\n".join(lines)

    def process_message(self, user_message: str, language: str = 'auto') -> Optional[str]:
        """Process user message and return skill suggestion"""
        # Auto-detect language
        if language == 'auto':
            korean_chars = len(re.findall(r'[ㄱ-ㅎㅏ-ㅣ가-힣]', user_message))
            language = 'ko' if korean_chars > len(user_message) * 0.1 else 'en'

        matches = self.detect_skills(user_message)

        if not matches:
            return None

        return self.format_suggestion(matches, language)

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all discovered skills"""
        return [
            {
                'name': s.name,
                'source': s.source,
                'path': str(s.path),
                'priority': s.priority,
                'description': s.description,
                'auto_activate': s.auto_activate
            }
            for s in self.skills.values()
        ]

    def get_skill_paths(self) -> List[Dict[str, str]]:
        """Get all skill search paths"""
        return [
            {'path': str(p), 'source': s}
            for p, s in self.skill_paths
        ]


# =============================================================================
# Output Formatters
# =============================================================================

def format_classic_output(skill: SkillMetadata, confidence: float) -> str:
    """Format output in classic mode (single skill, simple format)"""
    display_confidence = min(confidence, 1.0)  # Cap at 100% for display

    lines = [
        "<user-prompt-submit-hook>",
        "SKILL AUTO-ACTIVATED",
        "",
        "Based on your request, the following skill has been selected:",
        "",
        f"- **{skill.name}** (confidence: {int(display_confidence*100)}%)",
        f"  {skill.description}",
        "",
        f"ACTION REQUIRED: Use the Skill tool to activate `{skill.name}` before proceeding.",
        "",
        "User request follows:",
        "</user-prompt-submit-hook>"
    ]

    return "\n".join(lines)


def format_required_output(skill: SkillMetadata, confidence: float) -> str:
    """Format output for a required skill (shown alone, strong language)"""
    display_confidence = min(confidence, 1.0)

    lines = [
        "<user-prompt-submit-hook>",
        "⚠️ REQUIRED SKILL",
        "",
        "You MUST activate this skill before proceeding:",
        "",
        f"  • {skill.name} ({int(display_confidence*100)}% match)",
        f"    {skill.description}",
        "",
        f"ACTION: Use the Skill tool to activate `{skill.name}` BEFORE responding.",
        "",
        "User request follows:",
        "</user-prompt-submit-hook>"
    ]

    return "\n".join(lines)


def format_enhanced_output(matches: List[Tuple[SkillMetadata, float]], max_suggestions: int) -> str:
    """Format output in enhanced mode (multiple skills, grouped by enforcement)"""
    if not matches:
        return ""

    # Group by enforcement
    suggested = [(s, c) for s, c in matches if s.enforcement == "suggested"]
    optional = [(s, c) for s, c in matches if s.enforcement == "optional"]

    # Limit total to max_suggestions
    all_matches = []
    for s, c in suggested:
        if len(all_matches) < max_suggestions:
            all_matches.append((s, c, "suggested"))
    for s, c in optional:
        if len(all_matches) < max_suggestions:
            all_matches.append((s, c, "optional"))

    if not all_matches:
        return ""

    # Build output
    lines = ["<user-prompt-submit-hook>"]

    if len(all_matches) == 1:
        lines.append("SKILL SUGGESTION")
    else:
        lines.append("SKILL SUGGESTIONS")

    lines.append("")
    lines.append("Based on your request, these skills are relevant:")
    lines.append("")

    # Group by type for display
    suggested_items = [(s, c) for s, c, t in all_matches if t == "suggested"]
    optional_items = [(s, c) for s, c, t in all_matches if t == "optional"]

    if suggested_items:
        lines.append("📚 SUGGESTED:")
        for skill, conf in suggested_items:
            display_conf = min(conf, 1.0)
            lines.append(f"  • {skill.name} ({int(display_conf*100)}% match)")
            lines.append(f"    {skill.description}")
        lines.append("")

    if optional_items:
        lines.append("📌 OPTIONAL:")
        for skill, conf in optional_items:
            display_conf = min(conf, 1.0)
            lines.append(f"  • {skill.name} ({int(display_conf*100)}% match)")
            lines.append(f"    {skill.description}")
        lines.append("")

    # Action line
    if len(all_matches) == 1:
        skill = all_matches[0][0]
        lines.append(f"ACTION: Consider using the Skill tool to activate `{skill.name}`.")
    else:
        lines.append("ACTION: Consider using the Skill tool to activate relevant skills.")

    lines.append("")
    lines.append("User request follows:")
    lines.append("</user-prompt-submit-hook>")

    return "\n".join(lines)


# Hook integration for Claude Code
def user_prompt_submit_hook(user_message: str) -> str:
    """Hook function for Claude Code user-prompt-submit event"""
    try:
        # Load user configuration
        config = load_user_config()
        output_format = config.get("output_format", "classic")
        max_suggestions = config.get("max_suggestions", 3)

        activator = SkillActivator()
        matches = activator.detect_skills(user_message)

        if not matches:
            return ""

        # Classic mode: single best match, simple format
        if output_format == "classic":
            best_skill, confidence = matches[0]
            return format_classic_output(best_skill, confidence)

        # Enhanced mode: check for required skills first
        required_matches = [(s, c) for s, c in matches if s.enforcement == "required"]

        if required_matches:
            # Show only the best required skill, alone
            best_required, confidence = required_matches[0]
            return format_required_output(best_required, confidence)

        # No required skills - show multiple suggested/optional
        return format_enhanced_output(matches, max_suggestions)

    except Exception as e:
        print(f"Skill activator error: {e}", file=sys.stderr)
        return ""


def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if sys.platform == 'win32' else 'clear')


def save_config_to_env(config):
    """Save AI configuration to .env file"""
    env_path = Path(__file__).parent / '.env'

    # Read existing .env or create new
    existing_lines = []
    if env_path.exists():
        with open(env_path, 'r', encoding='utf-8') as f:
            existing_lines = f.readlines()

    # Settings to save
    settings = {
        'AI_PROVIDER': config.provider,
        'AI_MODEL': config.model,
        'AI_BASE_URL': config.base_url or '',
        'AI_LANGUAGES': ','.join(config.languages),
        'AI_FALLBACK_MODELS': ','.join(config.fallback_models) if config.fallback_models else '',
        'AI_RATE_LIMIT_RPM': str(config.rate_limit_rpm),
        'AI_RATE_LIMIT_DELAY': str(config.rate_limit_delay),
        'AI_MAX_RETRIES': str(config.max_retries),
        'AI_RETRY_DELAY': str(config.retry_delay),
    }

    # Update existing lines or add new ones
    updated_keys = set()
    new_lines = []

    for line in existing_lines:
        line_stripped = line.strip()
        # Skip empty lines and comments
        if not line_stripped or line_stripped.startswith('#'):
            new_lines.append(line)
            continue

        # Check if this line has a key we want to update
        if '=' in line_stripped:
            key = line_stripped.split('=')[0].strip()
            if key in settings:
                new_lines.append(f"{key}={settings[key]}\n")
                updated_keys.add(key)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)

    # Add any settings that weren't in the file
    for key, value in settings.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    # Write back
    with open(env_path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)


def interactive_wizard(activator: SkillActivator = None):
    """Interactive wizard for skill activator"""

    def print_header():
        print("\n" + "=" * 60)
        print("🎯  SKILL ACTIVATOR - Interactive Mode")
        print("=" * 60)

    def print_menu():
        print("\n📋 What would you like to do?\n")
        print("  [1] 🔍 Find skills for a task")
        print("  [2] 📚 List all available skills")
        print("  [3] 📂 Show skill search paths")
        print("  [4] ⚙️  Generate INDEX.yaml (AI)")
        print("  [5] 🧪 Test AI connection")
        print("  [6] 📦 Install to system")
        print("  [7] ❓ Help")
        print("  [q] 🚪 Quit")
        print()

    def get_choice(prompt: str, valid: list) -> str:
        while True:
            choice = input(prompt).strip().lower()
            if choice in valid:
                return choice
            print(f"  ⚠️  Invalid choice. Please enter one of: {', '.join(valid)}")

    def find_skills():
        print("\n" + "-" * 40)
        print("🔍 FIND SKILLS FOR A TASK")
        print("-" * 40)
        print("\nDescribe what you want to do:")
        print("(e.g., 'analyze ROI for my project', 'create documentation')\n")

        message = input("Your task: ").strip()
        if not message:
            print("  ⚠️  No input provided.")
            return

        # Get threshold
        threshold_input = input("\nConfidence threshold (0.1-1.0) [default: 0.5]: ").strip()
        try:
            threshold = float(threshold_input) if threshold_input else 0.5
            threshold = max(0.1, min(1.0, threshold))
        except ValueError:
            threshold = 0.5

        # Create activator with threshold
        local_activator = activator or SkillActivator(override_threshold=threshold)
        if activator:
            local_activator.override_threshold = threshold

        matches = local_activator.detect_skills(message)

        if matches:
            print("\n" + "=" * 40)
            print("✅ MATCHING SKILLS")
            print("=" * 40)
            for i, (skill, score) in enumerate(matches, 1):
                print(f"\n{i}. {skill.name}")
                print(f"   📊 Confidence: {score:.0%}")
                print(f"   📁 Source: {skill.source}")
                print(f"   📝 {skill.description[:80]}...")
        else:
            print("\n🔍 No matching skills found.")
            print("   Try lowering the confidence threshold or using different keywords.")

    def list_skills():
        print("\n" + "-" * 40)
        print("📚 AVAILABLE SKILLS")
        print("-" * 40)

        local_activator = activator or SkillActivator()
        skills = local_activator.list_skills()

        if not skills:
            print("\n  ⚠️  No skills found.")
            print("  Run option [4] to generate INDEX.yaml or add skills to:")
            for p in local_activator.get_skill_paths():
                print(f"    - {p['path']}")
            return

        print(f"\nFound {len(skills)} skills:\n")
        for s in skills:
            status = "✅" if s['auto_activate'] else "⏸️"
            print(f"  {status} {s['name']}")
            print(f"      [{s['source']}] {s['priority']} priority")
            print(f"      {s['description'][:60]}...")
            print()

    def show_paths():
        print("\n" + "-" * 40)
        print("📂 SKILL SEARCH PATHS")
        print("-" * 40)

        local_activator = activator or SkillActivator()
        paths = local_activator.get_skill_paths()

        print("\nSkills are searched in this order (first match wins):\n")
        if paths:
            for i, p in enumerate(paths, 1):
                exists = "✅" if Path(p['path']).exists() else "❌"
                print(f"  {i}. [{p['source']:7}] {exists} {p['path']}")
        else:
            print("  No skill paths configured.")

        print("\n💡 To add custom paths, set CLAUDE_SKILLS_PATH environment variable")

    def generate_index():
        print("\n" + "-" * 40)
        print("⚙️  GENERATE INDEX.yaml WITH AI")
        print("-" * 40)

        try:
            from index_generator import IndexGenerator, AIConfig
        except ImportError:
            print("\n  ❌ index_generator.py not found.")
            return

        config = AIConfig.from_env()

        print(f"\n📋 Current configuration (from .env):")
        print(f"  Provider:    {config.provider}")
        print(f"  Model:       {config.model}")
        print(f"  Base URL:    {config.base_url or 'default'}")
        print(f"  Languages:   {', '.join(config.languages)}")
        print(f"  Fallbacks:   {', '.join(config.fallback_models) if config.fallback_models else 'none'}")
        print(f"  Rate limit:  {config.rate_limit_rpm} req/min, {config.rate_limit_delay}s delay")
        print(f"  Retries:     {config.max_retries} attempts, {config.retry_delay}s delay")
        print(f"  API Key:     {'✅ Set' if config.api_key else '❌ Not set'}")

        if not config.api_key and config.provider != 'ollama':
            print("\n  ⚠️  API key not set. Edit .env file first.")
            return

        # Ask if user wants to customize
        print("\n" + "-" * 40)
        customize = input("Customize settings? [y/N]: ").strip().lower()

        if customize == 'y':
            # Provider
            print(f"\n1️⃣  AI Provider [{config.provider}]")
            print("   Options: openai, anthropic, ollama, openrouter, custom")
            new_provider = input("   Provider: ").strip().lower()
            if new_provider:
                config.provider = new_provider

            # Model
            print(f"\n2️⃣  AI Model [{config.model}]")
            print("   Examples: gpt-4o-mini, gpt-4o, claude-3-opus, llama3")
            new_model = input("   Model: ").strip()
            if new_model:
                config.model = new_model

            # Base URL
            print(f"\n3️⃣  Base URL [{config.base_url or 'default'}]")
            print("   Leave empty to use provider default")
            new_url = input("   URL: ").strip()
            if new_url:
                config.base_url = new_url

            # Languages
            print(f"\n4️⃣  Languages [{', '.join(config.languages)}]")
            print("   Examples: english | english,spanish | english,korean,japanese")
            new_langs = input("   Languages: ").strip()
            if new_langs:
                config.languages = [l.strip().lower() for l in new_langs.split(',')]

            # Fallback models
            print(f"\n5️⃣  Fallback Models [{', '.join(config.fallback_models) if config.fallback_models else 'none'}]")
            print("   Comma-separated list of backup models if primary fails")
            new_fallbacks = input("   Fallbacks: ").strip()
            if new_fallbacks:
                config.fallback_models = [m.strip() for m in new_fallbacks.split(',')]

            # Rate limiting
            print(f"\n6️⃣  Rate Limiting")
            new_rpm = input(f"   Requests per minute [{config.rate_limit_rpm}]: ").strip()
            if new_rpm:
                try:
                    config.rate_limit_rpm = int(new_rpm)
                except ValueError:
                    pass

            new_delay = input(f"   Min delay between requests (sec) [{config.rate_limit_delay}]: ").strip()
            if new_delay:
                try:
                    config.rate_limit_delay = float(new_delay)
                except ValueError:
                    pass

            # Retries
            print(f"\n7️⃣  Retry Settings")
            new_retries = input(f"   Max retries per model [{config.max_retries}]: ").strip()
            if new_retries:
                try:
                    config.max_retries = int(new_retries)
                except ValueError:
                    pass

            new_retry_delay = input(f"   Retry delay (sec) [{config.retry_delay}]: ").strip()
            if new_retry_delay:
                try:
                    config.retry_delay = float(new_retry_delay)
                except ValueError:
                    pass

        # Get skills path
        print("\n" + "-" * 40)
        print("📂 Skills Directory")
        default_path = "./skills"
        skills_path = input(f"   Path [{default_path}]: ").strip() or default_path

        if not Path(skills_path).exists():
            print(f"\n  ❌ Path does not exist: {skills_path}")
            return

        # Count skills
        skill_count = sum(1 for p in Path(skills_path).iterdir()
                         if p.is_dir() and (p / 'SKILL.md').exists())
        print(f"   Found {skill_count} skills with SKILL.md")

        if skill_count == 0:
            print("\n  ⚠️  No skills found. Make sure each skill has a SKILL.md file.")
            return

        # Get output path
        print("\n📄 Output File")
        default_output = str(Path(skills_path) / "INDEX.yaml")
        output_path = input(f"   Path [{default_output}]: ").strip() or default_output

        # Final summary
        print("\n" + "=" * 40)
        print("📋 SUMMARY")
        print("=" * 40)
        print(f"  Skills path:  {skills_path} ({skill_count} skills)")
        print(f"  Output:       {output_path}")
        print(f"  Provider:     {config.provider}")
        print(f"  Model:        {config.model}")
        print(f"  Base URL:     {config.base_url or 'default'}")
        print(f"  Languages:    {', '.join(config.languages)}")
        print(f"  Fallbacks:    {', '.join(config.fallback_models) if config.fallback_models else 'none'}")
        print(f"  Rate limit:   {config.rate_limit_rpm} req/min")
        print(f"  Retries:      {config.max_retries} attempts")

        # Estimate time
        est_time = skill_count * 10  # ~10 seconds per skill
        print(f"\n  ⏱️  Estimated time: ~{est_time // 60}m {est_time % 60}s")

        confirm = input("\n🚀 Start generation? [Y/n]: ").strip().lower()
        if confirm == 'n':
            print("  Cancelled.")
            return

        print("\n" + "-" * 40)
        generator = IndexGenerator(config)
        generator.generate_index(Path(skills_path), Path(output_path))

        # Offer to save config
        print("\n" + "-" * 40)
        save_config = input("💾 Save these settings to .env for next time? [y/N]: ").strip().lower()
        if save_config == 'y':
            save_config_to_env(config)
            print("  ✅ Settings saved to .env")

    def test_ai():
        print("\n" + "-" * 40)
        print("🧪 TEST AI CONNECTION")
        print("-" * 40)

        try:
            from index_generator import AIClient, AIConfig
        except ImportError:
            print("\n  ❌ index_generator.py not found.")
            return

        config = AIConfig.from_env()

        print(f"\nTesting connection to:")
        print(f"  Provider: {config.provider}")
        print(f"  Model: {config.model}")
        print(f"  Base URL: {config.base_url or 'default'}")
        print(f"  API Key: {config.api_key[:15]}...{config.api_key[-5:]}" if config.api_key else "  API Key: ❌ Not set")

        if not config.api_key and config.provider != 'ollama':
            print("\n  ⚠️  API key not set. Edit .env file first.")
            return

        print("\n⏳ Sending test request...")

        try:
            client = AIClient(config, debug=False)
            response = client.generate("Say 'Hello!' in one word.")
            print(f"\n✅ Success!")
            print(f"   Response: {response[:100]}")
        except Exception as e:
            print(f"\n❌ Failed: {e}")

    def run_install():
        print("\n" + "-" * 40)
        print("📦 INSTALL TO SYSTEM")
        print("-" * 40)

        try:
            from install import get_install_paths, install_activator, install_hook, create_example_skill, show_info
        except ImportError:
            print("\n  ❌ install.py not found.")
            return

        paths = get_install_paths()
        show_info(paths)

        print("\nWhat would you like to install?\n")
        print("  [1] Skill activator only")
        print("  [2] Skill activator + Claude hook")
        print("  [3] Everything (activator + hook + example skill)")
        print("  [b] Back to main menu")

        choice = get_choice("\nChoice: ", ['1', '2', '3', 'b'])

        if choice == 'b':
            return
        elif choice == '1':
            install_activator(paths)
        elif choice == '2':
            install_activator(paths)
            install_hook(paths)
        elif choice == '3':
            install_activator(paths)
            install_hook(paths)
            create_example_skill(paths)

    def show_help():
        print("\n" + "-" * 40)
        print("❓ HELP")
        print("-" * 40)

        print("""
🎯 SKILL ACTIVATOR

A keyword-based system that suggests relevant skills based on your task.

HOW IT WORKS:
1. Skills are defined in SKILL.md files with keywords
2. AI generates INDEX.yaml with optimized keywords (one-time)
3. When you describe a task, keywords are matched to suggest skills

QUICK START:
1. Run option [5] to test your AI connection
2. Run option [4] to generate INDEX.yaml for your skills
3. Run option [1] to find skills for a task

CONFIGURATION:
Edit .env file to configure:
  - AI_PROVIDER: openai, anthropic, ollama, openrouter
  - AI_MODEL: the model to use
  - AI_API_KEY: your API key
  - AI_LANGUAGES: languages for keywords (default: english)
  - AI_FALLBACK_MODELS: backup models if primary fails

SKILL FORMAT:
Each skill needs a SKILL.md file with YAML frontmatter:
  ---
  name: my-skill
  description: "What this skill does"
  keywords:
    english: [keyword1, keyword2]
  ---
  # Skill content here...

For more info, see README.md
        """)

    # Main wizard loop
    print_header()

    while True:
        print_menu()
        choice = get_choice("Enter choice: ", ['1', '2', '3', '4', '5', '6', '7', 'q'])

        if choice == 'q':
            print("\n👋 Goodbye!\n")
            break
        elif choice == '1':
            find_skills()
        elif choice == '2':
            list_skills()
        elif choice == '3':
            show_paths()
        elif choice == '4':
            generate_index()
        elif choice == '5':
            test_ai()
        elif choice == '6':
            run_install()
        elif choice == '7':
            show_help()

        input("\n⏎ Press Enter to continue...")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='Portable Skill Auto-Activator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "ROI analysis for my project"
  %(prog)s --list
  %(prog)s --paths
  %(prog)s --json "market strategy planning"
        """
    )

    parser.add_argument('message', nargs='?', help='User message to analyze')
    parser.add_argument('--list', '-l', action='store_true', help='List all discovered skills')
    parser.add_argument('--paths', '-p', action='store_true', help='Show skill search paths')
    parser.add_argument('--json', '-j', action='store_true', help='Output in JSON format')
    parser.add_argument('--project', help='Project directory path')
    parser.add_argument('--threshold', '-t', type=float,
                       help='Override confidence threshold (0.0-1.0)')
    parser.add_argument('--language', '-L', choices=['en', 'ko', 'auto'], default='auto',
                       help='Output language (default: auto)')

    # Index generation
    parser.add_argument('--generate-index', '-g', metavar='PATH',
                       help='Generate INDEX.yaml using AI (requires .env config)')
    parser.add_argument('--output', '-o', help='Output path for generated index')
    parser.add_argument('--test-ai', action='store_true', help='Test AI connection')
    parser.add_argument('--debug', '-d', action='store_true',
                       help='Enable debug logging (show full request/response)')
    parser.add_argument('--model', '-m', help='Override AI model (for testing)')
    parser.add_argument('--base-url', help='Override base URL (for testing)')
    parser.add_argument('--languages', help='Languages for keywords (comma-separated, e.g. "english,spanish")')
    parser.add_argument('--wizard', '-w', action='store_true', help='Launch interactive wizard')

    args = parser.parse_args()

    # Launch wizard if requested
    if args.wizard:
        interactive_wizard()
        return

    # Handle AI index generation
    if args.generate_index or args.test_ai:
        try:
            from index_generator import IndexGenerator, AIConfig
        except ImportError:
            print("❌ index_generator.py not found in the same directory")
            sys.exit(1)

        config = AIConfig.from_env()

        # Apply CLI overrides
        if args.model:
            config.model = args.model
        if args.base_url:
            config.base_url = args.base_url
        if args.languages:
            config.languages = [l.strip().lower() for l in args.languages.split(',')]

        if args.test_ai:
            print(f"Testing connection to {config.provider} / {config.model}...")
            print(f"Base URL: {config.base_url or 'default'}")
            print(f"API Key: {config.api_key[:15]}...{config.api_key[-5:]}" if config.api_key else "API Key: [not set]")
            print()
            try:
                from index_generator import AIClient
                client = AIClient(config, debug=args.debug)
                response = client.generate("Say 'Hello!' in one word.")
                print(f"\n✅ Success! Response: {response[:100]}")
            except Exception as e:
                print(f"\n❌ Failed: {e}")
                sys.exit(1)
            return

        if args.generate_index:
            generator = IndexGenerator(config)
            skills_path = Path(args.generate_index)
            output_path = Path(args.output) if args.output else None
            generator.generate_index(skills_path, output_path)
            return

    activator = SkillActivator(
        project_path=args.project,
        override_threshold=args.threshold
    )

    if args.paths:
        paths = activator.get_skill_paths()
        if args.json:
            print(json.dumps(paths, indent=2))
        else:
            print("\n📂 Skill Search Paths:\n")
            for p in paths:
                print(f"  [{p['source']:7}] {p['path']}")
            print()
        return

    if args.list:
        skills = activator.list_skills()
        if args.json:
            print(json.dumps(skills, indent=2))
        else:
            print(f"\n📚 Discovered Skills ({len(skills)} total):\n")
            for s in skills:
                status = "✅" if s['auto_activate'] else "⏸️"
                print(f"  {status} {s['name']:25} [{s['source']:7}] {s['priority']:6} - {s['description'][:50]}")
            print()
        return

    if not args.message:
        # Launch interactive wizard if no arguments
        interactive_wizard(activator)
        return

    if args.json:
        matches = activator.detect_skills(args.message)
        result = [
            {
                'skill': m.name,
                'source': m.source,
                'confidence': round(score, 3),
                'description': m.description,
                'path': str(m.path)
            }
            for m, score in matches
        ]
        print(json.dumps(result, indent=2))
    else:
        suggestion = activator.process_message(args.message, args.language)
        if suggestion:
            print(suggestion)
        else:
            print("🔍 No matching skills found.")


if __name__ == "__main__":
    main()
