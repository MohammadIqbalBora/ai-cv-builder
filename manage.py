#!/usr/bin/env python
# This command-line entry point runs Django management tasks. The shebang above
# lets Unix-like systems select Python when this file is executed directly.
"""Django's command-line utility for administrative tasks."""

# Import the `os` module for environment variable handling and path ops
import os

# Import the `sys` module to access `sys.argv` for CLI arguments
import sys


def main():
    """Set up the Django settings module and run the CLI command."""
    # Ensure the Django settings module environment variable is set
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

    try:
        # Import Django's command execution helper when available
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        # Raise a helpful error if Django isn't installed or importable
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Delegate to Django's command-line utility with current args
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    # Run `main` when the script is executed directly
    main()
