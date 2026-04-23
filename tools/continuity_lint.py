#!/usr/bin/env python3
"""Backward-compatible alias for chapter-level hard-rule linting."""

from chapter_hard_rules import main


if __name__ == "__main__":
    raise SystemExit(main())
