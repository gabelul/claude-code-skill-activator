#!/usr/bin/env python3
"""
Claude Code User Prompt Submit Hook
Auto-activates skills based on user message keywords
"""

import sys
import json
from pathlib import Path

def main():
    # Read JSON input from stdin
    try:
        input_data = json.load(sys.stdin)
        user_message = input_data.get('prompt', '')
    except (json.JSONDecodeError, KeyError):
        # If no valid JSON, exit silently
        sys.exit(0)

    if not user_message:
        sys.exit(0)

    # Try to load and run the skill activator
    activator_path = Path(__file__).parent.parent / 'skill_activator.py'

    if activator_path.exists():
        sys.path.insert(0, str(activator_path.parent))
        try:
            from skill_activator import user_prompt_submit_hook

            # Get skill context to inject
            additional_context = user_prompt_submit_hook(user_message)

            if additional_context:
                # Output as plain text - Claude Code will add it to context
                print(additional_context)

        except Exception as e:
            # Log error but don't block the message
            sys.stderr.write(f"Skill activator error: {e}\n")

    sys.exit(0)


if __name__ == "__main__":
    main()
