#!/usr/bin/env python3
"""
AI-Powered Skill Index Generator

Reads SKILL.md files and uses AI to extract:
- Keywords (Korean + English)
- Tags
- Use cases
- Priority level
- Confidence threshold

Supports multiple AI providers via .env configuration.
"""

import os
import re
import sys
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not required, can use env vars directly

# Try to import yaml
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False
    print("Warning: PyYAML not installed. Install with: pip install pyyaml")


@dataclass
class AIConfig:
    """AI provider configuration"""
    provider: str
    api_key: str
    model: str
    base_url: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.3
    timeout: int = 60
    fallback_models: List[str] = None
    rate_limit_rpm: int = 20  # requests per minute
    rate_limit_delay: float = 0.5  # minimum delay between requests
    max_retries: int = 3
    retry_delay: float = 2.0  # delay between retries
    languages: List[str] = None  # languages for keyword extraction

    def __post_init__(self):
        if self.fallback_models is None:
            self.fallback_models = []
        if self.languages is None:
            self.languages = ['english']

    @classmethod
    def from_env(cls) -> 'AIConfig':
        """Load configuration from environment variables"""
        fallback_str = os.getenv('AI_FALLBACK_MODELS', '')
        fallback_models = [m.strip() for m in fallback_str.split(',') if m.strip()]

        languages_str = os.getenv('AI_LANGUAGES', 'english')
        languages = [l.strip().lower() for l in languages_str.split(',') if l.strip()]

        provider = os.getenv('AI_PROVIDER', 'openai').lower()
        # Default model depends on provider - claude provider uses haiku by default
        default_model = 'haiku' if provider == 'claude' else 'gpt-4o-mini'
        model = os.getenv('AI_MODEL', default_model)

        return cls(
            provider=provider,
            api_key=os.getenv('AI_API_KEY', ''),
            model=model,
            base_url=os.getenv('AI_BASE_URL', '').strip() or None,
            max_tokens=int(os.getenv('AI_MAX_TOKENS', '2000')),
            temperature=float(os.getenv('AI_TEMPERATURE', '0.3')),
            timeout=int(os.getenv('AI_TIMEOUT', '60')),
            fallback_models=fallback_models,
            rate_limit_rpm=int(os.getenv('AI_RATE_LIMIT_RPM', '20')),
            rate_limit_delay=float(os.getenv('AI_RATE_LIMIT_DELAY', '0.5')),
            max_retries=int(os.getenv('AI_MAX_RETRIES', '3')),
            retry_delay=float(os.getenv('AI_RETRY_DELAY', '2.0')),
            languages=languages
        )


class RateLimiter:
    """Simple rate limiter to prevent API overload"""

    def __init__(self, rpm: int = 20, min_delay: float = 0.5):
        self.rpm = rpm
        self.min_delay = min_delay
        self.request_times: List[float] = []
        self.last_request_time: float = 0

    def wait_if_needed(self):
        """Wait if we're hitting rate limits"""
        now = time.time()

        # Always enforce minimum delay between requests
        time_since_last = now - self.last_request_time
        if time_since_last < self.min_delay:
            sleep_time = self.min_delay - time_since_last
            time.sleep(sleep_time)
            now = time.time()

        # Clean old request times (older than 1 minute)
        self.request_times = [t for t in self.request_times if now - t < 60]

        # If we've hit RPM limit, wait until oldest request is 1 minute old
        if len(self.request_times) >= self.rpm:
            oldest = self.request_times[0]
            wait_time = 60 - (now - oldest) + 0.1  # +0.1 buffer
            if wait_time > 0:
                print(f"⏳ Rate limit reached ({self.rpm} RPM). Waiting {wait_time:.1f}s...")
                time.sleep(wait_time)
                now = time.time()
                self.request_times = [t for t in self.request_times if now - t < 60]

        # Record this request
        self.request_times.append(now)
        self.last_request_time = now


class AIClient:
    """Multi-provider AI client with fallback and rate limiting"""

    # Default base URLs
    DEFAULT_URLS = {
        'openai': 'https://api.openai.com/v1',
        'anthropic': 'https://api.anthropic.com',
        'ollama': 'http://localhost:11434',
        'openrouter': 'https://openrouter.ai/api/v1',
    }

    def __init__(self, config: AIConfig, debug: bool = False):
        self.config = config
        self.debug = debug
        self.base_url = config.base_url or self.DEFAULT_URLS.get(config.provider, '')
        self.rate_limiter = RateLimiter(
            rpm=config.rate_limit_rpm,
            min_delay=config.rate_limit_delay
        )
        self.current_model = config.model  # Track which model we're using

    def _log(self, *args, **kwargs):
        """Print debug info if debug mode is on"""
        if self.debug:
            print(*args, **kwargs)

    def _request(self, messages: List[Dict], system: str = None) -> str:
        """Make API request based on provider"""
        provider = self.config.provider

        if provider == 'claude':
            return self._claude_cli_request(messages, system)
        elif provider == 'anthropic':
            return self._anthropic_request(messages, system)
        elif provider == 'ollama':
            return self._ollama_request(messages, system)
        else:
            # OpenAI-compatible (openai, openrouter, custom)
            return self._openai_request(messages, system)

    def _claude_cli_request(self, messages: List[Dict], system: str = None) -> str:
        """Use Claude Code CLI with Haiku model (no API key needed)"""
        import subprocess

        # Build the prompt from messages
        prompt_parts = []
        if system:
            prompt_parts.append(f"System: {system}\n")
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            prompt_parts.append(f"{role.capitalize()}: {content}")

        full_prompt = "\n".join(prompt_parts)

        # Use model from config (default haiku) or allow override
        model = self.config.model if self.config.model != 'gpt-4o-mini' else 'haiku'

        try:
            result = subprocess.run(
                ['claude', '--model', model, '--dangerously-skip-permissions', '-p', full_prompt],
                capture_output=True,
                text=True,
                timeout=self.config.timeout
            )

            if result.returncode != 0:
                raise RuntimeError(f"Claude CLI error: {result.stderr}")

            return result.stdout.strip()

        except FileNotFoundError:
            raise RuntimeError("Claude CLI not found. Install Claude Code or use a different provider.")
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Claude CLI timeout after {self.config.timeout}s")

    def _openai_request(self, messages: List[Dict], system: str = None) -> str:
        """OpenAI-compatible API request"""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/chat/completions"

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": all_messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }

        headers = {
            "Content-Type": "application/json",
        }

        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        # OpenRouter specific headers
        if self.config.provider == 'openrouter':
            headers["HTTP-Referer"] = "https://github.com/skill-activator"
            headers["X-Title"] = "Skill Index Generator"

        # Debug logging
        self._log("\n" + "="*60)
        self._log("REQUEST")
        self._log("="*60)
        self._log(f"URL: {url}")
        self._log(f"Method: POST")
        self._log(f"\nHeaders:")
        for k, v in headers.items():
            # Mask API key
            if k == "Authorization":
                v = v[:20] + "..." + v[-10:] if len(v) > 30 else "[HIDDEN]"
            self._log(f"  {k}: {v}")
        self._log(f"\nPayload:")
        debug_payload = payload.copy()
        # Truncate messages for display
        if 'messages' in debug_payload:
            debug_payload['messages'] = [
                {**m, 'content': m['content'][:200] + '...' if len(m.get('content', '')) > 200 else m.get('content', '')}
                for m in debug_payload['messages']
            ]
        self._log(json.dumps(debug_payload, indent=2, ensure_ascii=False))

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                response_body = response.read().decode('utf-8')

                self._log("\n" + "="*60)
                self._log("RESPONSE")
                self._log("="*60)
                self._log(f"Status: {response.status}")
                self._log(f"Headers:")
                for k, v in response.headers.items():
                    self._log(f"  {k}: {v}")
                self._log(f"\nBody:")
                self._log(response_body[:2000] + ('...' if len(response_body) > 2000 else ''))
                self._log("="*60 + "\n")

                result = json.loads(response_body)
                return result['choices'][0]['message']['content']
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''

            self._log("\n" + "="*60)
            self._log("ERROR RESPONSE")
            self._log("="*60)
            self._log(f"Status: {e.code}")
            self._log(f"Reason: {e.reason}")
            self._log(f"Headers:")
            for k, v in e.headers.items():
                self._log(f"  {k}: {v}")
            self._log(f"\nBody:")
            self._log(error_body)
            self._log("="*60 + "\n")

            raise Exception(f"API error {e.code}: {error_body}")

    def _anthropic_request(self, messages: List[Dict], system: str = None) -> str:
        """Anthropic API request"""
        import urllib.request
        import urllib.error

        url = f"{self.base_url}/v1/messages"

        payload = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": messages,
        }

        if system:
            payload["system"] = system

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01"
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
                result = json.loads(response.read().decode('utf-8'))
                return result['content'][0]['text']
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else ''
            raise Exception(f"API error {e.code}: {error_body}")

    def _ollama_request(self, messages: List[Dict], system: str = None) -> str:
        """Ollama API request"""
        import urllib.request

        url = f"{self.base_url}/api/chat"

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        payload = {
            "model": self.config.model,
            "messages": all_messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"},
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=self.config.timeout) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result['message']['content']

    def generate(self, prompt: str, system: str = None) -> str:
        """Generate response from AI with retry and fallback support"""
        messages = [{"role": "user", "content": prompt}]

        # Build list of models to try: primary + fallbacks
        models_to_try = [self.config.model] + (self.config.fallback_models or [])

        last_error = None

        for model_idx, model in enumerate(models_to_try):
            self.current_model = model

            for retry in range(self.config.max_retries):
                try:
                    # Apply rate limiting
                    self.rate_limiter.wait_if_needed()

                    self._log(f"\n🔄 Attempt {retry + 1}/{self.config.max_retries} with model: {model}")

                    return self._request_with_model(messages, system, model)

                except Exception as e:
                    last_error = e
                    error_str = str(e)

                    # Check if it's a rate limit error (429) - wait longer
                    if '429' in error_str or 'rate' in error_str.lower():
                        wait_time = self.config.retry_delay * (retry + 1) * 2  # Exponential backoff
                        self._log(f"⚠️ Rate limited. Waiting {wait_time:.1f}s before retry...")
                        time.sleep(wait_time)
                        continue

                    # Check if it's a model not found error (404) - skip to next model
                    if '404' in error_str or 'not found' in error_str.lower():
                        self._log(f"⚠️ Model '{model}' not found. Trying next fallback...")
                        break  # Break retry loop, try next model

                    # Check if it's a server error (5xx) - retry with backoff
                    if any(code in error_str for code in ['500', '502', '503', '504']):
                        wait_time = self.config.retry_delay * (retry + 1)
                        self._log(f"⚠️ Server error. Waiting {wait_time:.1f}s before retry...")
                        time.sleep(wait_time)
                        continue

                    # Other errors - retry with normal delay
                    if retry < self.config.max_retries - 1:
                        self._log(f"⚠️ Error: {e}. Retrying in {self.config.retry_delay}s...")
                        time.sleep(self.config.retry_delay)
                    else:
                        self._log(f"❌ All retries failed for model '{model}'")

            # If we have more models to try, log and continue
            if model_idx < len(models_to_try) - 1:
                next_model = models_to_try[model_idx + 1]
                print(f"🔄 Switching from '{model}' to fallback model '{next_model}'...")

        # All models and retries exhausted
        raise Exception(f"All models failed. Last error: {last_error}")

    def _request_with_model(self, messages: List[Dict], system: str, model: str) -> str:
        """Make request with a specific model"""
        # Temporarily set the model
        original_model = self.config.model
        self.config.model = model
        try:
            return self._request(messages, system)
        finally:
            self.config.model = original_model


class IndexGenerator:
    """AI-powered skill index generator"""

    SYSTEM_PROMPT_TEMPLATE = """You are a skill metadata extractor. Given a skill document, extract structured metadata for keyword-based skill matching.

Your task is to analyze the skill content and generate:
1. Keywords in the following languages: {languages}
2. Tags for categorization
3. Use cases describing when to use this skill
4. Intent patterns (regex) for matching complex user requests
5. Priority level (high/medium/low) based on skill importance
6. A confidence threshold (0.5-0.9) - higher means more strict matching

Output ONLY valid JSON, no markdown, no explanation. Use this exact format:
{{
  "keywords": {{
{keywords_format}
  }},
  "tags": ["tag1", "tag2", ...],
  "use_cases": ["Sentence starting with -ing verb", ...],
  "intent_patterns": ["regex pattern 1", "regex pattern 2", ...],
  "priority": "high|medium|low",
  "confidence_threshold": 0.7,
  "description": "One-line description of when to use this skill"
}}

CRITICAL KEYWORD GUIDELINES:
- ONLY include keywords that are CORE to this skill's primary purpose
- DO NOT include generic keywords that could apply to many unrelated skills
- Example: A debugging skill should include: debug, debugging, error, trace, bug
- Example: A debugging skill should NOT include: validation, security (not core)
- Use SIMPLE, SHORT words (1-2 words max) that users would actually type
- Include the ROOT word AND its common forms: debug, debugging, debugger
- Extract 15-25 simple keywords per language
- Include both nouns AND verbs: analyze, plan, calculate, research

CRITICAL USE_CASES GUIDELINES (VERY IMPORTANT FOR MATCHING):
- Use cases determine WHEN the skill activates - they are used for matching\!
- ALWAYS start each use case with a present participle verb (-ing form)
- ALWAYS include the skill's PRIMARY ACTION VERB in at least one use case
- Example for debugging skill: Debugging errors that occur in production code
- Include 4-6 concrete use cases
- BAD: When you have a problem (too vague)
- GOOD: Debugging intermittent test failures in CI/CD pipelines

INTENT_PATTERNS GUIDELINES (regex for complex matching):
- Generate 2-4 regex patterns for common ways users phrase requests
- Patterns are case-insensitive Python regex
- Example for code review: ["review.*code", "check.*for.*issues"]
- Example for debugging: ["fix.*bug", "debug.*error", "trace.*issue"]
- Use .* for flexible matching between words

Other guidelines:
- Tags should be general categories (max 5)
- Priority: high = core/frequently used, medium = specialized, low = niche
- Confidence threshold: 0.5-0.6 for general skills, 0.7+ for specific skills"""

    def __init__(self, config: AIConfig = None):
        self.config = config or AIConfig.from_env()
        self.client = AIClient(self.config)
        self.system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build system prompt based on configured languages"""
        languages = self.config.languages

        # Format languages for prompt
        languages_str = ', '.join(languages)

        # Build keywords format example
        keywords_lines = []
        for lang in languages:
            keywords_lines.append(f'    "{lang}": ["keyword1", "keyword2", ...]')
        keywords_format = ',\n'.join(keywords_lines)

        return self.SYSTEM_PROMPT_TEMPLATE.format(
            languages=languages_str,
            keywords_format=keywords_format
        )

    def extract_skill_metadata(self, skill_content: str, skill_name: str, verbose: bool = True) -> Dict:
        """Extract metadata from a skill document using AI"""
        prompt = f"""Analyze this skill document and extract metadata:

Skill Name: {skill_name}

Content:
---
{skill_content[:8000]}
---

Remember: Output ONLY valid JSON, no markdown code blocks."""

        try:
            if verbose:
                print(f"ACTIVITY:Waiting for AI response...", flush=True)

            response = self.client.generate(prompt, self.system_prompt)

            if verbose:
                print(f"ACTIVITY:Processing response...", flush=True)

            # Clean response - remove markdown code blocks if present
            response = response.strip()
            if response.startswith('```'):
                response = re.sub(r'^```\w*\n?', '', response)
                response = re.sub(r'\n?```$', '', response)

            return json.loads(response)
        except json.JSONDecodeError as e:
            if verbose:
                print(f"ACTIVITY:Parse error - retrying...", flush=True)
            return None
        except Exception as e:
            if verbose:
                print(f"ACTIVITY:Error - {str(e)[:50]}", flush=True)
            return None

    def scan_skills_directory(self, skills_path: Path) -> Dict[str, Path]:
        """Scan directory for skills (folders with SKILL.md)"""
        skills = {}

        if not skills_path.exists():
            return skills

        for item in skills_path.iterdir():
            if item.is_dir():
                skill_md = item / 'SKILL.md'
                if skill_md.exists():
                    skills[item.name] = skill_md

        return skills

    def generate_index(self,
                      skills_path: Path,
                      output_path: Path = None,
                      verbose: bool = True,
                      skills_filter: List[str] = None) -> Dict:
        """Generate INDEX.yaml from skill files

        Args:
            skills_path: Path to skills directory
            output_path: Output file path (default: skills_path/INDEX.yaml)
            verbose: Show progress output
            skills_filter: Optional list of skill names to process (default: all)
        """

        if output_path is None:
            output_path = skills_path / 'INDEX.yaml'

        all_skills = self.scan_skills_directory(skills_path)

        # Filter skills if specified
        if skills_filter:
            skills = {k: v for k, v in all_skills.items() if k in skills_filter}
            if verbose and len(skills) < len(skills_filter):
                missing = set(skills_filter) - set(skills.keys())
                for m in missing:
                    print(f"STATUS:WARNING:{m}:Skill not found", flush=True)
        else:
            skills = all_skills

        if not skills:
            print(f"No skills found in {skills_path}")
            return {}

        if verbose:
            print(f"\n🔍 Found {len(skills)} skills in {skills_path}")
            print(f"🤖 Using AI: {self.config.provider} / {self.config.model}")
            print(f"🌐 Languages: {', '.join(self.config.languages)}")
            print(f"📝 Output: {output_path}\n")

        # Load existing index if doing selective update
        existing_index = None
        if skills_filter and output_path.exists():
            try:
                if HAS_YAML:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        existing_index = yaml.safe_load(f)
                else:
                    with open(output_path, 'r', encoding='utf-8') as f:
                        existing_index = json.load(f)
            except Exception:
                pass  # Will create new index

        # Build index structure (or use existing)
        if existing_index and 'skills' in existing_index:
            index = existing_index
            if verbose:
                print(f"ACTIVITY:Merging with existing index ({len(index.get('skills', {}))} skills)", flush=True)
        else:
            index = {
                "version": "1.0",
                "generated_by": "ai-index-generator",
                "ai_provider": self.config.provider,
                "ai_model": self.config.model,
                "activation_config": {
                    "mode": "suggest",
                    "confidence_threshold": 0.5,
                    "max_suggestions": 3,
                    "priority_multipliers": {
                        "high": 1.5,
                        "medium": 1.0,
                        "low": 0.7
                    }
                },
                "keyword_weights": {
                    "exact_match": 3.0,
                    "compound_match": 2.5,
                    "partial_match": 1.5,
                    "tag_match": 0.8,
                    "use_case_match": 2.0
                },
                "skills": {}
            }

        # Process each skill
        for i, (skill_name, skill_path) in enumerate(skills.items(), 1):
            if verbose:
                # Output progress in machine-parseable format for installer
                print(f"PROGRESS:{i}:{len(skills)}:{skill_name}", flush=True)

            try:
                content = skill_path.read_text(encoding='utf-8')
            except Exception as e:
                if verbose:
                    print(f"STATUS:ERROR:{skill_name}:Read error - {e}", flush=True)
                continue

            # Extract metadata using AI
            if verbose:
                print(f"ACTIVITY:Sending to AI...", flush=True)
            metadata = self.extract_skill_metadata(content, skill_name, verbose=verbose)

            if metadata:
                # Build default keywords structure based on configured languages
                default_keywords = {lang: [] for lang in self.config.languages}
                keywords = metadata.get("keywords", default_keywords)

                # Count keywords for verbose output
                total_keywords = sum(len(v) for v in keywords.values() if isinstance(v, list))

                index["skills"][skill_name] = {
                    "priority": metadata.get("priority", "medium"),
                    "description": metadata.get("description", ""),
                    "keywords": keywords,
                    "tags": metadata.get("tags", []),
                    "use_cases": metadata.get("use_cases", []),
                    "intent_patterns": metadata.get("intent_patterns", []),
                    "auto_activate": True,
                    "confidence_threshold": metadata.get("confidence_threshold", 0.7)
                }
                if verbose:
                    print(f"STATUS:OK:{skill_name}:{total_keywords} keywords", flush=True)
            else:
                # Fallback: basic metadata with configured languages
                fallback_keywords = {lang: [] for lang in self.config.languages}
                # Add skill name as keyword in first language
                if self.config.languages:
                    fallback_keywords[self.config.languages[0]] = [skill_name.replace('-', ' ')]

                index["skills"][skill_name] = {
                    "priority": "medium",
                    "description": f"Skill: {skill_name}",
                    "keywords": fallback_keywords,
                    "tags": [],
                    "use_cases": [],
                    "auto_activate": True,
                    "confidence_threshold": 0.7
                }
                if verbose:
                    print(f"STATUS:FALLBACK:{skill_name}:using fallback metadata", flush=True)

            # Small delay to avoid rate limits
            if i < len(skills):
                time.sleep(0.5)

        # Write output
        if HAS_YAML:
            with open(output_path, 'w', encoding='utf-8') as f:
                yaml.dump(index, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
        else:
            # Fallback to JSON
            output_path = output_path.with_suffix('.json')
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(index, f, ensure_ascii=False, indent=2)

        if verbose:
            print(f"COMPLETE:{len(index['skills'])}:{output_path}", flush=True)

        return index


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='AI-Powered Skill Index Generator',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s ./skills                    # Generate INDEX.yaml in ./skills
  %(prog)s ./skills -o custom.yaml     # Custom output path
  %(prog)s ./skills --provider ollama  # Use Ollama
  %(prog)s --test                      # Test AI connection
        """
    )

    parser.add_argument('skills_path', nargs='?', default='./skills',
                       help='Path to skills directory')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('--skills', help='Comma-separated list of skill names to index (default: all)')
    parser.add_argument('--provider', help='AI provider (overrides .env)')
    parser.add_argument('--model', help='AI model (overrides .env)')
    parser.add_argument('--api-key', help='API key (overrides .env)')
    parser.add_argument('--base-url', help='Base URL (overrides .env)')
    parser.add_argument('--test', action='store_true', help='Test AI connection')
    parser.add_argument('--quiet', '-q', action='store_true', help='Minimal output')

    args = parser.parse_args()

    # Build config from env + overrides
    config = AIConfig.from_env()

    if args.provider:
        config.provider = args.provider.lower()
    if args.model:
        config.model = args.model
    if args.api_key:
        config.api_key = args.api_key
    if args.base_url:
        config.base_url = args.base_url

    # Validate config
    if config.provider not in ['ollama'] and not config.api_key:
        print("❌ Error: AI_API_KEY not set")
        print("   Set it in .env file or use --api-key")
        print("   Or use --provider ollama for local models")
        sys.exit(1)

    # Test mode
    if args.test:
        print(f"Testing connection to {config.provider} / {config.model}...")
        try:
            client = AIClient(config)
            response = client.generate("Say 'Hello, Skill Activator!' in exactly those words.")
            print(f"✅ Success! Response: {response[:100]}")
        except Exception as e:
            print(f"❌ Failed: {e}")
            sys.exit(1)
        return

    # Generate index
    generator = IndexGenerator(config)
    skills_path = Path(args.skills_path)
    output_path = Path(args.output) if args.output else None

    # Parse skills filter if provided
    skills_filter = None
    if args.skills:
        skills_filter = [s.strip() for s in args.skills.split(',') if s.strip()]

    generator.generate_index(
        skills_path=skills_path,
        output_path=output_path,
        verbose=not args.quiet,
        skills_filter=skills_filter
    )


if __name__ == "__main__":
    main()
