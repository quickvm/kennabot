#!/usr/bin/env python3
"""Legacy import script — use the CLI instead.

This script has been replaced by the KennaBot CLI.
Run one of the following commands instead:

    kennabot plusplus import-hubot --from-file <file> [--dry-run]
    kennabot plusplus import-hubot --redis-url <url> [--redis-key <key>] [--dry-run]
"""

from __future__ import annotations

import sys

print(__doc__.strip())
sys.exit(1)
