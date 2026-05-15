#!/usr/bin/env python3
"""Documentation: how the Instinct reskin pre/post visual baselines were captured.

These screenshots are not produced by this script — they are captured by the
agent driving the Playwright MCP tools against a running web UI. This file
documents the procedure so the runs are reproducible.

Run the web UI:
    venv/bin/python aippt.py serve --port 8000

For each of the nine views below, capture both light and dark themes by
toggling `document.documentElement.dataset.theme` between 'light' and 'dark'
before each screenshot:

    01-deck-list       /                       (default landing)
    02-search-results  Search tab + run a query
    03-settings        Settings tab
    04-slide-browser   Click into a deck, slide grid visible
    05-slide-modal     Click a slide thumbnail, modal open
    06-tags            Tags tab
    07-create-deck     Decks tab, expand "Create Deck from Outline"
    08-view-only       Restart server with AIPPT_VIEW_ONLY=1
    09-mobile          viewport 375x812

Save to:
    tests/visual-baselines/pre-instinct/NN-<view>-<theme>.png   (before any CSS changes)
    tests/visual-baselines/post-instinct/NN-<view>-<theme>.png  (after Instinct reskin)

Use fullPage=true and type='png'. Compare pre vs post visually during the
per-view QA tasks (PRD tasks 11–19).
"""

if __name__ == "__main__":
    print(__doc__)
