#!/usr/bin/env python3
"""Thin wrapper — delegates to aippt.cli.

For backwards compatibility, this script supports both:
- New subcommand syntax: aippt.py create outline.md template.pptx output.pptx
- Legacy positional syntax: aippt.py outline.md template.pptx output.pptx
"""
import sys


def main():
    """Entry point supporting both old and new CLI syntax."""
    from aippt.cli import main as cli_main, build_parser

    # Check if using legacy positional syntax (no subcommand)
    # Legacy: aippt.py outline.md template.pptx output.pptx [options]
    # New: aippt.py create outline.md template.pptx output.pptx [options]
    if len(sys.argv) > 1 and not sys.argv[1].startswith('-'):
        subcommands = {'create', 'reverse', 'catalog', 'search', 'remix', 'analyze', 'export', 'export-images', 'serve', 'storage', 'models', 'ingest', 'tags', 'tag', 'untag', 'decks', 'improve', 'write-notes', 'db-info', 'migrate-paths', 'merge', 'merge-template', 'mcp', 'metadata'}
        if sys.argv[1] not in subcommands:
            # Legacy mode - insert 'create' as the subcommand
            sys.argv.insert(1, 'create')

    return cli_main()


if __name__ == "__main__":
    sys.exit(main() or 0)
