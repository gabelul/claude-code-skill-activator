#!/usr/bin/env python3
"""
Skill Activator Installer
Installs the portable skill activator to user's system

Usage:
  python install.py              # Interactive install
  python install.py --user       # Install to user directory only
  python install.py --hook       # Also install Claude Code hook
  python install.py --uninstall  # Remove installation
"""

import os
import sys
import shutil
import argparse
import subprocess
import venv
from pathlib import Path

# Required packages for index generation
REQUIRED_PACKAGES = ['pyyaml', 'python-dotenv']

# =============================================================================
# Terminal Styling
# =============================================================================

class Style:
    """Terminal colors and styling"""
    # Check if terminal supports colors
    SUPPORTS_COLOR = (
        hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
        and os.environ.get('TERM') != 'dumb'
        and os.environ.get('NO_COLOR') is None
    )

    # Colors
    RESET = '\033[0m' if SUPPORTS_COLOR else ''
    BOLD = '\033[1m' if SUPPORTS_COLOR else ''
    DIM = '\033[2m' if SUPPORTS_COLOR else ''

    # Foreground colors
    RED = '\033[91m' if SUPPORTS_COLOR else ''
    GREEN = '\033[92m' if SUPPORTS_COLOR else ''
    YELLOW = '\033[93m' if SUPPORTS_COLOR else ''
    BLUE = '\033[94m' if SUPPORTS_COLOR else ''
    MAGENTA = '\033[95m' if SUPPORTS_COLOR else ''
    CYAN = '\033[96m' if SUPPORTS_COLOR else ''
    WHITE = '\033[97m' if SUPPORTS_COLOR else ''

    @classmethod
    def success(cls, text: str) -> str:
        return f"{cls.GREEN}{text}{cls.RESET}"

    @classmethod
    def error(cls, text: str) -> str:
        return f"{cls.RED}{text}{cls.RESET}"

    @classmethod
    def warning(cls, text: str) -> str:
        return f"{cls.YELLOW}{text}{cls.RESET}"

    @classmethod
    def info(cls, text: str) -> str:
        return f"{cls.CYAN}{text}{cls.RESET}"

    @classmethod
    def highlight(cls, text: str) -> str:
        return f"{cls.BOLD}{cls.WHITE}{text}{cls.RESET}"

    @classmethod
    def dim(cls, text: str) -> str:
        return f"{cls.DIM}{text}{cls.RESET}"


def print_banner():
    """Print the installer banner"""
    s = Style
    banner = f"""
{s.CYAN}{s.BOLD}    _____ __   _ ____              __  _            __            {s.RESET}
{s.CYAN}{s.BOLD}   / ___// /__(_) / /    ___  ____/ /_(_)   ______ / /_____  _____{s.RESET}
{s.CYAN}{s.BOLD}   \\__ \\/ //_/ / / /    / _ \\/ __/ __/ / | / / __ `/ __/ __ \\/ ___/{s.RESET}
{s.CYAN}{s.BOLD}  ___/ / ,< / / / /    /  __/ /_/ /_/ /| |/ / /_/ / /_/ /_/ / /    {s.RESET}
{s.CYAN}{s.BOLD} /____/_/|_/_/_/_/     \\___/\\__/\\__/_/ |___/\\__,_/\\__/\\____/_/     {s.RESET}

{s.DIM}  Portable Skill Activator for Claude Code{s.RESET}
{s.DIM}  ─────────────────────────────────────────{s.RESET}
{s.DIM}  by gabel @ Booplex{s.RESET}
"""
    print(banner)


def print_section(title: str):
    """Print a section header"""
    s = Style
    print(f"\n{s.BOLD}{s.BLUE}▸ {title}{s.RESET}")
    print(f"{s.DIM}{'─' * (len(title) + 2)}{s.RESET}")


def print_step(text: str, status: str = "info"):
    """Print a step with status indicator"""
    s = Style
    icons = {
        "info": f"{s.CYAN}○{s.RESET}",
        "success": f"{s.GREEN}✓{s.RESET}",
        "error": f"{s.RED}✗{s.RESET}",
        "warning": f"{s.YELLOW}!{s.RESET}",
        "pending": f"{s.DIM}○{s.RESET}",
    }
    icon = icons.get(status, icons["info"])
    print(f"  {icon} {text}")


def print_path(label: str, path: Path, exists: bool = None):
    """Print a path with optional existence indicator"""
    s = Style
    if exists is None:
        exists = path.exists()

    status = f"{s.GREEN}exists{s.RESET}" if exists else f"{s.DIM}not found{s.RESET}"
    print(f"  {s.DIM}│{s.RESET} {label}: {s.CYAN}{path}{s.RESET} [{status}]")


# =============================================================================
# Virtual Environment Management
# =============================================================================

def get_venv_path() -> Path:
    """Get path to the virtual environment"""
    return Path(__file__).parent / '.venv'


def get_venv_python() -> Path:
    """Get path to the venv Python executable"""
    venv_path = get_venv_path()
    if sys.platform == 'win32':
        return venv_path / 'Scripts' / 'python.exe'
    return venv_path / 'bin' / 'python'


def is_venv_active() -> bool:
    """Check if we're running inside the venv"""
    venv_path = get_venv_path()
    return sys.prefix == str(venv_path) or sys.prefix == str(venv_path.resolve())


def check_dependencies() -> dict:
    """Check which required packages are installed"""
    status = {}
    for package in REQUIRED_PACKAGES:
        try:
            # Map package names to import names
            import_name = package.replace('-', '_')
            if package == 'pyyaml':
                import_name = 'yaml'
            elif package == 'python-dotenv':
                import_name = 'dotenv'

            __import__(import_name)
            status[package] = True
        except ImportError:
            status[package] = False
    return status


def setup_venv(verbose: bool = True) -> bool:
    """Create virtual environment and install dependencies"""
    s = Style
    venv_path = get_venv_path()
    venv_python = get_venv_python()

    try:
        # Create venv if it doesn't exist
        if not venv_path.exists():
            if verbose:
                print_step("Creating virtual environment...", "info")

            venv.create(venv_path, with_pip=True)

            if verbose:
                print_step(f"Created .venv at {venv_path}", "success")

        # Check if venv python exists
        if not venv_python.exists():
            if verbose:
                print_step("Virtual environment is corrupted, recreating...", "warning")
            shutil.rmtree(venv_path)
            venv.create(venv_path, with_pip=True)

        # Install required packages
        missing = [pkg for pkg, installed in check_dependencies_in_venv().items() if not installed]

        if missing:
            if verbose:
                print_step(f"Installing dependencies: {', '.join(missing)}", "info")

            # Upgrade pip first (quietly)
            subprocess.run(
                [str(venv_python), '-m', 'pip', 'install', '--upgrade', 'pip', '-q'],
                capture_output=True
            )

            # Install packages
            result = subprocess.run(
                [str(venv_python), '-m', 'pip', 'install'] + missing + ['-q'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                if verbose:
                    print_step(f"Failed to install packages: {result.stderr}", "error")
                return False

            if verbose:
                print_step("Dependencies installed", "success")
        else:
            if verbose:
                print_step("All dependencies already installed", "success")

        return True

    except Exception as e:
        if verbose:
            print_step(f"Failed to setup virtual environment: {e}", "error")
        return False


def check_dependencies_in_venv() -> dict:
    """Check which required packages are installed in the venv"""
    venv_python = get_venv_python()
    if not venv_python.exists():
        return {pkg: False for pkg in REQUIRED_PACKAGES}

    status = {}
    for package in REQUIRED_PACKAGES:
        # Map package names to import names
        import_name = package.replace('-', '_')
        if package == 'pyyaml':
            import_name = 'yaml'
        elif package == 'python-dotenv':
            import_name = 'dotenv'

        result = subprocess.run(
            [str(venv_python), '-c', f'import {import_name}'],
            capture_output=True
        )
        status[package] = result.returncode == 0

    return status


def ensure_venv_ready(verbose: bool = True, show_section: bool = True) -> bool:
    """Ensure venv exists and has all dependencies"""
    s = Style
    venv_path = get_venv_path()

    # Check if venv exists and has dependencies
    if venv_path.exists():
        deps = check_dependencies_in_venv()
        if all(deps.values()):
            return True  # All good

    # Need to setup
    if verbose and show_section:
        print_section("Environment Setup")
        print(f"  {s.DIM}Setting up Python environment for AI index generation...{s.RESET}")
        print()

    return setup_venv(verbose)


# =============================================================================
# Path Utilities
# =============================================================================

def get_user_skill_path() -> Path:
    """Get user-specific skill directory - ~/.claude/skills/ on all platforms"""
    return Path.home() / '.claude' / 'skills'


def get_user_hooks_path() -> Path:
    """Get user hooks directory for Claude Code - ~/.claude/hooks/ on all platforms"""
    return Path.home() / '.claude' / 'hooks'


def get_install_paths() -> dict:
    """Get all relevant installation paths"""
    script_dir = Path(__file__).parent
    src_dir = script_dir / 'src'

    return {
        'source': script_dir,
        'src_dir': src_dir,
        'source_activator': src_dir / 'skill_activator.py',
        'source_index_generator': src_dir / 'index_generator.py',
        'user_skills': get_user_skill_path(),
        'user_hooks': get_user_hooks_path(),
        'activator_dest': get_user_skill_path().parent / 'skill_activator.py',
        'index_generator_dest': get_user_skill_path().parent / 'index_generator.py',
        'hook_dest': get_user_hooks_path() / 'user-prompt-submit.py',
    }


# =============================================================================
# Installation Status
# =============================================================================

def get_installation_status(paths: dict) -> dict:
    """Check what's currently installed"""
    venv_path = get_venv_path()

    status = {
        'activator_installed': paths['activator_dest'].exists(),
        'index_generator_installed': paths['index_generator_dest'].exists(),
        'hook_installed': paths['hook_dest'].exists(),
        'skills_dir_exists': paths['user_skills'].exists(),
        'skill_count': 0,
        'has_index': False,
        'ai_configured': is_ai_configured(),
        'venv_exists': venv_path.exists(),
        'deps_installed': False,
    }

    if status['skills_dir_exists']:
        status['skill_count'] = sum(
            1 for d in paths['user_skills'].iterdir()
            if d.is_dir() and (d / 'SKILL.md').exists()
        )
        status['has_index'] = (paths['user_skills'] / 'INDEX.yaml').exists()

    # Check venv dependencies (only if venv exists to avoid slow check)
    if status['venv_exists']:
        deps = check_dependencies_in_venv()
        status['deps_installed'] = all(deps.values())

    return status


def print_status(paths: dict, status: dict):
    """Print current installation status"""
    s = Style

    print_section("Current Installation Status")

    # Core components
    if status['activator_installed'] and status['hook_installed']:
        print_step("Core components installed", "success")
    elif status['activator_installed'] or status['hook_installed']:
        print_step("Partially installed", "warning")
    else:
        print_step("Not installed", "pending")

    print()
    print_path("Activator", paths['activator_dest'], status['activator_installed'])
    print_path("Hook", paths['hook_dest'], status['hook_installed'])
    print_path("Skills folder", paths['user_skills'], status['skills_dir_exists'])

    # Skills info
    if status['skill_count'] > 0:
        print(f"  {s.DIM}│{s.RESET} Skills found: {s.GREEN}{status['skill_count']}{s.RESET}")
        if status['has_index']:
            print(f"  {s.DIM}│{s.RESET} INDEX.yaml: {s.GREEN}present{s.RESET}")
        else:
            print(f"  {s.DIM}│{s.RESET} INDEX.yaml: {s.YELLOW}missing{s.RESET}")

    # AI config
    if status['ai_configured']:
        print(f"  {s.DIM}│{s.RESET} AI config: {s.GREEN}configured{s.RESET}")
    else:
        print(f"  {s.DIM}│{s.RESET} AI config: {s.DIM}not configured{s.RESET}")

    # Venv status
    if status['venv_exists'] and status['deps_installed']:
        print(f"  {s.DIM}│{s.RESET} Environment: {s.GREEN}ready{s.RESET}")
    elif status['venv_exists']:
        print(f"  {s.DIM}│{s.RESET} Environment: {s.YELLOW}missing dependencies{s.RESET}")
    else:
        print(f"  {s.DIM}│{s.RESET} Environment: {s.DIM}not set up{s.RESET} {s.DIM}(will auto-create){s.RESET}")

    print()


# =============================================================================
# Configuration Checks
# =============================================================================

def get_ai_config() -> dict:
    """Get AI configuration from .env"""
    script_dir = Path(__file__).parent
    env_file = script_dir / '.env'

    config = {
        'configured': False,
        'provider': None,
        'model': None,
        'base_url': None,
    }

    if not env_file.exists():
        return config

    content = env_file.read_text()

    has_key = False

    for line in content.splitlines():
        line = line.strip()
        if line.startswith('#'):
            continue
        if line.startswith('AI_API_KEY='):
            value = line.split('=', 1)[1].strip()
            placeholders = ['your-key', 'your_key', 'changeme', 'replace-me', 'insert-key']
            has_key = bool(value) and not any(p in value.lower() for p in placeholders)
        elif line.startswith('AI_PROVIDER='):
            config['provider'] = line.split('=', 1)[1].strip()
        elif line.startswith('AI_MODEL='):
            config['model'] = line.split('=', 1)[1].strip()
        elif line.startswith('AI_BASE_URL='):
            config['base_url'] = line.split('=', 1)[1].strip()

    config['configured'] = has_key and bool(config['provider'])
    return config


def is_ai_configured() -> bool:
    """Check if AI is configured in .env"""
    return get_ai_config()['configured']


# =============================================================================
# Installation Functions
# =============================================================================

def render_progress_bar(current: int, total: int, width: int = 30, skill_name: str = "", activity: str = "") -> str:
    """Render a progress bar string with optional activity status"""
    s = Style
    if total == 0:
        return ""

    percentage = current / total
    filled = int(width * percentage)
    empty = width - filled

    # Progress bar characters
    bar = f"{s.GREEN}{'█' * filled}{s.DIM}{'░' * empty}{s.RESET}"
    percent_str = f"{int(percentage * 100):3d}%"

    # Truncate skill name if too long
    max_name_len = 25
    if len(skill_name) > max_name_len:
        skill_name = skill_name[:max_name_len-2] + ".."

    # Build the line
    line = f"  {bar} {s.BOLD}{percent_str}{s.RESET} [{current}/{total}] {s.CYAN}{skill_name}{s.RESET}"

    # Add activity on same line if provided
    if activity:
        # Truncate activity if needed
        max_activity_len = 30
        if len(activity) > max_activity_len:
            activity = activity[:max_activity_len-2] + ".."
        line += f" {s.DIM}- {activity}{s.RESET}"

    # Pad to clear previous content (in case previous line was longer)
    line += " " * 20

    return line


def generate_index(skills_path: Path, verbose: bool = True, skills_filter: list = None) -> bool:
    """Generate INDEX.yaml for a skills folder with live progress bar

    Args:
        skills_path: Path to skills directory
        verbose: Show progress output
        skills_filter: Optional list of skill names to index (None = all)
    """
    s = Style

    try:
        script_dir = Path(__file__).parent
        activator = script_dir / 'src' / 'skill_activator.py'

        if not activator.exists():
            if verbose:
                print_step(f"skill_activator.py not found in src/", "error")
            return False

        # Ensure venv is ready with dependencies (quietly if already set up)
        venv_path = get_venv_path()
        needs_setup = not venv_path.exists() or not all(check_dependencies_in_venv().values())

        if needs_setup:
            if not ensure_venv_ready(verbose, show_section=True):
                if verbose:
                    print_step("Cannot generate index without dependencies", "error")
                return False

        if verbose:
            print()
            if skills_filter:
                print_step(f"Generating INDEX.yaml for {len(skills_filter)} selected skills", "info")
            else:
                print_step(f"Generating INDEX.yaml for: {skills_path}", "info")
            print()

            # Show AI provider info
            ai_config = get_ai_config()
            provider = ai_config.get('provider', 'unknown')
            model = ai_config.get('model', 'default')
            base_url = ai_config.get('base_url', '')

            print(f"  {s.DIM}Calling AI to extract keywords for each skill...{s.RESET}")
            print()
            print(f"  {s.DIM}│ Provider: {s.CYAN}{provider}{s.RESET}")
            print(f"  {s.DIM}│ Model:    {s.CYAN}{model}{s.RESET}")
            if base_url:
                # Truncate long URLs
                display_url = base_url if len(base_url) <= 40 else base_url[:37] + "..."
                print(f"  {s.DIM}│ Endpoint: {s.CYAN}{display_url}{s.RESET}")
            print()

        # Run with venv Python for dependencies
        venv_python = get_venv_python()

        # Use UTF-8 encoding explicitly for Windows compatibility
        env = os.environ.copy()
        env['PYTHONIOENCODING'] = 'utf-8'

        # Build command
        cmd = [str(venv_python), str(activator), '--generate-index', str(skills_path)]

        # Add skills filter if specified
        if skills_filter:
            cmd.extend(['--skills', ','.join(skills_filter)])

        process = subprocess.Popen(
            cmd,
            cwd=str(script_dir),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            errors='replace',  # Replace undecodable chars instead of crashing
            bufsize=1,  # Line buffered
            env=env,
        )

        # Track progress
        current_skill = ""
        current_activity = ""
        total_skills = 0
        processed = 0
        results = []  # Store results for summary

        # Stream output and parse progress
        while True:
            line = process.stdout.readline()
            if not line and process.poll() is not None:
                break
            if line:
                line = line.rstrip()

                # Parse machine-readable progress output
                if line.startswith("PROGRESS:"):
                    # Format: PROGRESS:current:total:skill_name
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        processed = int(parts[1])
                        total_skills = int(parts[2])
                        current_skill = parts[3]
                        current_activity = ""  # Reset activity for new skill
                        if verbose:
                            # Clear line and print progress bar
                            print(f"\r{render_progress_bar(processed, total_skills, skill_name=current_skill, activity=current_activity)}", end="", flush=True)

                elif line.startswith("ACTIVITY:"):
                    # Format: ACTIVITY:message
                    current_activity = line.split(":", 1)[1] if ":" in line else ""
                    if verbose and total_skills > 0:
                        print(f"\r{render_progress_bar(processed, total_skills, skill_name=current_skill, activity=current_activity)}", end="", flush=True)

                elif line.startswith("STATUS:"):
                    # Format: STATUS:OK|FALLBACK|ERROR:skill_name:message
                    parts = line.split(":", 3)
                    if len(parts) >= 4:
                        status = parts[1]
                        skill = parts[2]
                        msg = parts[3]
                        results.append((status, skill, msg))

                elif line.startswith("COMPLETE:"):
                    # Format: COMPLETE:count:path
                    parts = line.split(":", 2)
                    if len(parts) >= 3:
                        final_count = parts[1]
                        output_path = parts[2]

                elif not line.startswith(("🔍", "🤖", "🌐", "📝", "✅", "📁")):
                    # Other output (errors, warnings, etc)
                    if verbose and line.strip():
                        print(f"\n  {s.DIM}│ {line}{s.RESET}", end="", flush=True)

        process.wait()

        # Clear progress line and show results
        if verbose and total_skills > 0:
            # Final progress bar at 100%
            print(f"\r{render_progress_bar(total_skills, total_skills, skill_name='Done!')}")
            print()

            # Summary
            ok_count = sum(1 for r in results if r[0] == "OK")
            fallback_count = sum(1 for r in results if r[0] == "FALLBACK")

            if ok_count > 0:
                print_step(f"{ok_count} skills indexed successfully", "success")
            if fallback_count > 0:
                print_step(f"{fallback_count} skills used fallback metadata", "warning")

        if process.returncode == 0:
            if verbose:
                print_step("INDEX.yaml generated", "success")
            return True
        else:
            if verbose:
                print()
                print_step("Failed to generate index", "error")
            return False

    except Exception as e:
        if verbose:
            print()
            print_step(f"Error generating index: {e}", "error")
        return False


def install_activator(paths: dict, verbose: bool = True) -> bool:
    """Install the skill activator to user directory"""
    try:
        paths['user_skills'].mkdir(parents=True, exist_ok=True)

        shutil.copy2(paths['source_activator'], paths['activator_dest'])
        if verbose:
            print_step(f"Installed skill_activator.py", "success")

        shutil.copy2(paths['source_index_generator'], paths['index_generator_dest'])
        if verbose:
            print_step(f"Installed index_generator.py", "success")

        return True
    except Exception as e:
        if verbose:
            print_step(f"Failed to install activator: {e}", "error")
        return False


def configure_settings_json(hook_path: Path, global_install: bool = True, verbose: bool = True) -> bool:
    """Configure settings.json to register the hook"""
    try:
        import json

        if global_install:
            settings_path = Path.home() / '.claude' / 'settings.json'
        else:
            settings_path = Path.cwd() / '.claude' / 'settings.json'

        settings_path.parent.mkdir(parents=True, exist_ok=True)

        if settings_path.exists():
            with open(settings_path, 'r', encoding='utf-8') as f:
                settings = json.load(f)
        else:
            settings = {}

        hook_command = f'python "{hook_path}"'

        hooks = settings.get('hooks', {})
        user_prompt_hooks = hooks.get('UserPromptSubmit', [])

        already_configured = False
        for hook_group in user_prompt_hooks:
            for hook in hook_group.get('hooks', []):
                if hook.get('command', '').find('user-prompt-submit.py') != -1:
                    already_configured = True
                    break

        if not already_configured:
            new_hook = {
                'hooks': [{
                    'type': 'command',
                    'command': hook_command
                }]
            }
            user_prompt_hooks.append(new_hook)
            hooks['UserPromptSubmit'] = user_prompt_hooks
            settings['hooks'] = hooks

            with open(settings_path, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2)

            if verbose:
                print_step(f"Configured hook in settings.json", "success")
        else:
            if verbose:
                print_step(f"Hook already configured in settings.json", "info")

        return True
    except Exception as e:
        if verbose:
            print_step(f"Failed to configure settings.json: {e}", "error")
        return False


def install_hook(paths: dict, verbose: bool = True, force: bool = False) -> bool:
    """Install Claude Code hook"""
    try:
        paths['user_hooks'].mkdir(parents=True, exist_ok=True)

        hook_content = '''#!/usr/bin/env python3
"""
Claude Code User Prompt Submit Hook
Auto-activates skills based on user message keywords
"""

import sys
from pathlib import Path

# Add skill activator to path
activator_path = Path(__file__).parent.parent / 'skill_activator.py'
if activator_path.exists():
    sys.path.insert(0, str(activator_path.parent))
    from skill_activator import user_prompt_submit_hook

    def hook(user_message: str) -> str:
        return user_prompt_submit_hook(user_message)
else:
    def hook(user_message: str) -> str:
        return user_message

if __name__ == "__main__":
    if len(sys.argv) > 1:
        message = " ".join(sys.argv[1:])
        print(hook(message))
'''

        if paths['hook_dest'].exists() and not force:
            print_step(f"Hook already exists at {paths['hook_dest']}", "warning")
            response = input(f"    Overwrite? [y/N]: ").strip().lower()
            if response != 'y':
                print_step("Skipped hook installation", "info")
                return False

        paths['hook_dest'].write_text(hook_content, encoding='utf-8')

        if verbose:
            print_step(f"Installed hook", "success")

        configure_settings_json(paths['hook_dest'], global_install=True, verbose=verbose)

        return True
    except Exception as e:
        if verbose:
            print_step(f"Failed to install hook: {e}", "error")
        return False


def uninstall(paths: dict, verbose: bool = True) -> bool:
    """Remove installation"""
    s = Style

    if verbose:
        print_section("Uninstalling")

    removed = []

    if paths['activator_dest'].exists():
        paths['activator_dest'].unlink()
        removed.append('skill_activator.py')

    if paths['index_generator_dest'].exists():
        paths['index_generator_dest'].unlink()
        removed.append('index_generator.py')

    if paths['hook_dest'].exists():
        paths['hook_dest'].unlink()
        removed.append('hook')

    if verbose:
        if removed:
            for r in removed:
                print_step(f"Removed {r}", "success")
            print()
            print(f"  {s.DIM}Note: Your skills folder was preserved:{s.RESET}")
            print(f"  {s.CYAN}{paths['user_skills']}{s.RESET}")
        else:
            print_step("Nothing to uninstall", "info")

    return True


# =============================================================================
# Info Display
# =============================================================================

def show_info(paths: dict):
    """Show installation information"""
    s = Style

    print_section("Installation Paths")
    print(f"  {s.DIM}│{s.RESET} Activator:  {s.CYAN}{paths['activator_dest']}{s.RESET}")
    print(f"  {s.DIM}│{s.RESET} Hook:       {s.CYAN}{paths['hook_dest']}{s.RESET}")
    print(f"  {s.DIM}│{s.RESET} Skills:     {s.CYAN}{paths['user_skills']}{s.RESET}")

    print_section("Environment Variable")
    print(f"  {s.DIM}│{s.RESET} {s.BOLD}CLAUDE_SKILLS_PATH{s.RESET} - Add custom skill directories")
    if sys.platform == 'win32':
        print(f"  {s.DIM}│{s.RESET} Example: {s.DIM}set CLAUDE_SKILLS_PATH=C:\\MySkills;D:\\MoreSkills{s.RESET}")
    else:
        print(f"  {s.DIM}│{s.RESET} Example: {s.DIM}export CLAUDE_SKILLS_PATH=/path/to/skills:/another/path{s.RESET}")

    print_section("Skill Search Order")
    print(f"  {s.DIM}│{s.RESET} {s.BOLD}1.{s.RESET} Project local:  {s.DIM}./.claude/skills/ or ./skills/{s.RESET}")
    print(f"  {s.DIM}│{s.RESET} {s.BOLD}2.{s.RESET} User global:    {s.DIM}{paths['user_skills']}{s.RESET}")
    print(f"  {s.DIM}│{s.RESET} {s.BOLD}3.{s.RESET} Custom paths:   {s.DIM}CLAUDE_SKILLS_PATH{s.RESET}")

    print_section("Quick Start")
    print(f"  {s.DIM}│{s.RESET} 1. Create a skill folder in {s.CYAN}{paths['user_skills']}{s.RESET}")
    print(f"  {s.DIM}│{s.RESET} 2. Add {s.BOLD}SKILL.md{s.RESET} with YAML frontmatter")
    print(f"  {s.DIM}│{s.RESET} 3. Run: {s.DIM}python skill_activator.py --generate-index{s.RESET}")
    print()


# =============================================================================
# Project Setup
# =============================================================================

def setup_project_skills(project_path: Path, verbose: bool = True) -> bool:
    """Set up skills for a specific project - generates INDEX if skills exist"""
    s = Style

    try:
        skills_dir = project_path / 'skills'
        alt_skills_dir = project_path / '.claude' / 'skills'

        if skills_dir.exists() and any(skills_dir.iterdir()):
            target = skills_dir
        elif alt_skills_dir.exists() and any(alt_skills_dir.iterdir()):
            target = alt_skills_dir
        else:
            skills_dir.mkdir(parents=True, exist_ok=True)
            if verbose:
                print_step(f"Created skills folder: {skills_dir}", "success")
                print(f"  {s.DIM}Add your skill folders here, each with a SKILL.md file.{s.RESET}")
                print(f"  {s.DIM}Then run: python skill_activator.py --generate-index{s.RESET}")
            return True

        skill_count = sum(1 for d in target.iterdir() if d.is_dir() and (d / 'SKILL.md').exists())
        if skill_count > 0:
            if verbose:
                print_step(f"Found {skill_count} skills in: {target}", "success")

            index_file = target / 'INDEX.yaml'

            if index_file.exists():
                if verbose:
                    print_step("INDEX.yaml already exists", "info")
                response = input("    Regenerate? [y/N]: ").strip().lower()
                if response == 'y':
                    prompt_generate_index(target, skill_count)
            else:
                if verbose:
                    print_step("No INDEX.yaml found", "warning")
                prompt_generate_index(target, skill_count)

        return True
    except Exception as e:
        print_step(f"Failed to set up project skills: {e}", "error")
        return False


# =============================================================================
# Interactive Wizard
# =============================================================================

def prompt_generate_index(skills_path: Path, skill_count: int) -> bool:
    """Prompt user to generate INDEX.yaml with optional skill selection

    Returns True if index was generated, False otherwise
    """
    s = Style

    if not is_ai_configured():
        print(f"  {s.DIM}Configure AI in .env to generate INDEX.yaml{s.RESET}")
        return False

    print()
    print(f"  {s.BOLD}Generate INDEX.yaml?{s.RESET}")
    print()
    print(f"  {s.BOLD}[1]{s.RESET} Yes - index all {skill_count} skills")
    print(f"  {s.BOLD}[2]{s.RESET} Yes - select specific skills")
    print(f"  {s.BOLD}[3]{s.RESET} No - skip for now")
    print()

    choice = prompt_choice("Choose", range(1, 4), default=1)

    if choice == 1:
        generate_index(skills_path)
        return True
    elif choice == 2:
        selected = select_skills_to_index(skills_path)
        if selected:
            generate_index(skills_path, skills_filter=selected)
            return True
        else:
            print_step("No skills selected", "info")
            return False
    else:
        print_step("Skipped INDEX.yaml generation", "info")
        return False


def get_available_skills(skills_path: Path) -> list:
    """Get list of available skill names"""
    skills = []
    if skills_path.exists():
        for item in skills_path.iterdir():
            if item.is_dir() and (item / 'SKILL.md').exists():
                skills.append(item.name)
    return sorted(skills)


def select_skills_to_index(skills_path: Path) -> list:
    """Interactive skill selection for indexing"""
    s = Style
    skills = get_available_skills(skills_path)

    if not skills:
        return []

    print()
    print(f"  {s.DIM}Enter skill numbers separated by commas, or ranges like 1-5{s.RESET}")
    print(f"  {s.DIM}Press Enter to cancel{s.RESET}")
    print()

    # Display skills with numbers
    for i, skill in enumerate(skills, 1):
        # Check if already in INDEX.yaml
        index_file = skills_path / 'INDEX.yaml'
        indexed = False
        if index_file.exists():
            try:
                content = index_file.read_text(encoding='utf-8')
                indexed = f"{skill}:" in content or f'"{skill}"' in content
            except:
                pass

        status_indicator = f"{s.GREEN}✓{s.RESET}" if indexed else f"{s.DIM}○{s.RESET}"
        print(f"  {status_indicator} {s.BOLD}[{i:2d}]{s.RESET} {skill}")

    print()
    print(f"  {s.DIM}Legend: {s.GREEN}✓{s.RESET} = already indexed, {s.DIM}○{s.RESET} = not indexed{s.RESET}")
    print()

    selection = input(f"  Select skills: ").strip()

    if not selection:
        return []

    # Parse selection (supports: 1,2,3 or 1-5 or 1,3-5,7)
    selected_indices = set()
    try:
        for part in selection.split(','):
            part = part.strip()
            if '-' in part:
                start, end = part.split('-', 1)
                for i in range(int(start), int(end) + 1):
                    selected_indices.add(i)
            else:
                selected_indices.add(int(part))
    except ValueError:
        print_step("Invalid selection format", "error")
        return []

    # Convert to skill names
    selected_skills = []
    for idx in sorted(selected_indices):
        if 1 <= idx <= len(skills):
            selected_skills.append(skills[idx - 1])

    if selected_skills:
        print()
        print_step(f"Selected {len(selected_skills)} skills: {', '.join(selected_skills[:3])}{'...' if len(selected_skills) > 3 else ''}", "info")

    return selected_skills


def prompt_choice(prompt: str, options: list, default: int = None) -> int:
    """Prompt user for a choice from numbered options"""
    s = Style

    while True:
        if default is not None:
            response = input(f"{prompt} [{default}]: ").strip()
            if not response:
                return default
        else:
            response = input(f"{prompt}: ").strip()

        try:
            choice = int(response)
            if 1 <= choice <= len(options):
                return choice
            print(f"  {s.DIM}Please enter a number between 1 and {len(options)}{s.RESET}")
        except ValueError:
            print(f"  {s.DIM}Please enter a number{s.RESET}")


def interactive_install(paths: dict):
    """Interactive installation wizard"""
    s = Style

    print_banner()

    # Ensure venv is ready on startup (silent if already good)
    venv_path = get_venv_path()
    if not venv_path.exists() or not all(check_dependencies_in_venv().values()):
        ensure_venv_ready(verbose=True, show_section=True)
        print()

    # Check current status
    status = get_installation_status(paths)
    print_status(paths, status)

    # Determine what to show based on status
    is_installed = status['activator_installed'] and status['hook_installed']

    print_section("What would you like to do?")
    print()

    if is_installed:
        # Already installed - show different options
        print(f"  {s.BOLD}[1]{s.RESET} Reinstall / Update")
        print(f"      {s.DIM}Reinstall activator and hook with latest version{s.RESET}")
        print()
        print(f"  {s.BOLD}[2]{s.RESET} Generate INDEX.yaml")
        print(f"      {s.DIM}Regenerate skill index for keyword matching{s.RESET}")
        print()
        print(f"  {s.BOLD}[3]{s.RESET} Set up project skills")
        print(f"      {s.DIM}Initialize skills for a specific project{s.RESET}")
        print()
        print(f"  {s.BOLD}[4]{s.RESET} Uninstall")
        print(f"      {s.DIM}Remove activator and hook (keeps your skills){s.RESET}")
        print()
        print(f"  {s.BOLD}[5]{s.RESET} Exit")
        print()

        choice = prompt_choice("Choose an option", range(1, 6), default=5)

        if choice == 1:
            # Reinstall - full installation
            print_section("Reinstalling")

            # Update venv/dependencies
            print_step("Updating environment...", "info")
            setup_venv(verbose=True)
            print()

            # Reinstall scripts
            install_activator(paths)
            install_hook(paths, force=True)

            print()
            print(f"  {s.GREEN}Installation updated!{s.RESET}")

            # Offer to regenerate INDEX if skills exist
            if status['skill_count'] > 0:
                print()
                response = input(f"  Regenerate INDEX.yaml for {status['skill_count']} skills? [y/N]: ").strip().lower()
                if response == 'y':
                    prompt_generate_index(paths['user_skills'], status['skill_count'])

        elif choice == 2:
            # Generate index
            print_section("Generate INDEX.yaml")
            if status['skill_count'] > 0:
                # Ask if they want all or select specific skills
                print(f"  {s.BOLD}[1]{s.RESET} Index all {status['skill_count']} skills")
                print(f"  {s.BOLD}[2]{s.RESET} Select specific skills to index")
                print()
                index_choice = prompt_choice("Choose", range(1, 3), default=1)

                if not is_ai_configured():
                    print_step("AI not configured in .env", "warning")
                    print(f"  {s.DIM}Configure AI_PROVIDER and AI_API_KEY in .env first{s.RESET}")
                elif index_choice == 1:
                    generate_index(paths['user_skills'])
                else:
                    # Let user select skills
                    selected = select_skills_to_index(paths['user_skills'])
                    if selected:
                        generate_index(paths['user_skills'], skills_filter=selected)
                    else:
                        print_step("No skills selected", "info")
            else:
                print_step("No skills found to index", "warning")

        elif choice == 3:
            # Project setup
            print_section("Project Setup")
            default_path = Path.cwd()
            project_input = input(f"  Project path [{s.DIM}{default_path}{s.RESET}]: ").strip()

            if project_input:
                project_path = Path(project_input).expanduser().resolve()
            else:
                project_path = default_path

            if not project_path.exists():
                print_step(f"Path does not exist: {project_path}", "error")
            else:
                setup_project_skills(project_path)

        elif choice == 4:
            # Uninstall
            response = input(f"  {s.YELLOW}Are you sure you want to uninstall? [y/N]:{s.RESET} ").strip().lower()
            if response == 'y':
                uninstall(paths)
            else:
                print_step("Uninstall cancelled", "info")

        elif choice == 5:
            print()
            print(f"  {s.DIM}Goodbye!{s.RESET}")

    else:
        # Not installed - show install options
        print(f"  {s.BOLD}[1]{s.RESET} Install {s.GREEN}(recommended){s.RESET}")
        print(f"      {s.DIM}Install activator + hook to ~/.claude/{s.RESET}")
        print(f"      {s.DIM}Enables skill activation for all projects{s.RESET}")
        print()
        print(f"  {s.BOLD}[2]{s.RESET} Install + Set up project")
        print(f"      {s.DIM}Install globally and configure a specific project{s.RESET}")
        print()
        print(f"  {s.BOLD}[3]{s.RESET} Exit")
        print()

        choice = prompt_choice("Choose an option", range(1, 4), default=1)

        if choice == 1:
            # Install
            print_section("Installing")
            install_activator(paths)
            install_hook(paths)

            # Check for existing skills
            if status['skill_count'] > 0 and not status['has_index']:
                print()
                print_step(f"Found {status['skill_count']} existing skills", "info")
                prompt_generate_index(paths['user_skills'], status['skill_count'])

            print()
            print(f"  {s.GREEN}{s.BOLD}Installation complete!{s.RESET}")
            print()
            show_info(paths)

        elif choice == 2:
            # Install + project
            print_section("Installing")
            install_activator(paths)
            install_hook(paths)

            print_section("Project Setup")
            default_path = Path.cwd()
            project_input = input(f"  Project path [{s.DIM}{default_path}{s.RESET}]: ").strip()

            if project_input:
                project_path = Path(project_input).expanduser().resolve()
            else:
                project_path = default_path

            if not project_path.exists():
                print_step(f"Path does not exist: {project_path}", "error")
            else:
                setup_project_skills(project_path)

            print()
            print(f"  {s.GREEN}{s.BOLD}Installation complete!{s.RESET}")
            print()
            show_info(paths)

        elif choice == 3:
            print()
            print(f"  {s.DIM}Goodbye!{s.RESET}")

    print()


# =============================================================================
# Main Entry Point
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Skill Activator Installer',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--user', action='store_true',
                       help='Install activator to user directory')
    parser.add_argument('--hook', action='store_true',
                       help='Also install Claude Code hook')
    parser.add_argument('--uninstall', action='store_true',
                       help='Remove installation')
    parser.add_argument('--info', action='store_true',
                       help='Show installation paths')
    parser.add_argument('--quiet', '-q', action='store_true',
                       help='Suppress output')

    args = parser.parse_args()
    paths = get_install_paths()

    verbose = not args.quiet

    if args.info:
        print_banner()
        show_info(paths)
        return

    if args.uninstall:
        print_banner()
        uninstall(paths, verbose)
        return

    if args.user or args.hook:
        # Non-interactive mode
        print_banner()
        print_section("Installing")
        if args.user:
            install_activator(paths, verbose)
        if args.hook:
            install_hook(paths, verbose)
        if verbose:
            print()
            show_info(paths)
    else:
        # Interactive mode
        interactive_install(paths)


if __name__ == "__main__":
    main()
