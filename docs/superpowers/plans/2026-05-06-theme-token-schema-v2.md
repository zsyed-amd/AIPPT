# Theme Token Schema v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the pptxgenjs theme YAML schema from 15 to 49 fields, replacing ~40 hardcoded design decisions with theme-driven tokens and adding a `createDeck()` overrides mechanism.

**Architecture:** Add a `TOKEN_DEFAULTS` constant and `deepMerge()` utility to `loadTheme()`. New token sections (typography, data_colors, shadow, eyebrow) plus expanded color slots merge with defaults. `createDeck()` accepts an `overrides` option that deep-merges over the loaded theme. Slide builders read from `theme.*` instead of hardcoded values.

**Tech Stack:** Node.js ESM (`.mjs`), pptxgenjs, YAML themes, Python/pytest for tests

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `lib/pptxgenjs-helpers.mjs` | Modify | `TOKEN_DEFAULTS`, `deepMerge()`, expanded `loadTheme()`, `createDeck()` overrides, `cardShadow(theme)`, typography/color/eyebrow token reads in all slide builders |
| `lib/pptxgenjs-masters.mjs` | Modify | Footer fontSize reads `theme.typography.footer_size` |
| `themes/default.yaml` | Modify | Add new token sections matching current hardcoded defaults |
| `themes/amd.yaml` | Modify | Add new token sections matching current hardcoded defaults |
| `themes/instinct.yaml` | Modify | Add new token sections with design system values |
| `tests/test_theme_tokens.py` | Create | Token defaults, YAML overrides, createDeck overrides, backward compat |

---

### Task 1: Write theme token tests

**Files:**
- Create: `tests/test_theme_tokens.py`

These tests validate the token resolution system. They'll fail initially because the token sections don't exist yet in `loadTheme()`.

- [ ] **Step 1: Create test file with all test cases**

```python
"""Tests for theme token schema v2 — typography, shadow, eyebrow, data_colors, overrides."""

import subprocess
import json
import os
import pytest

HELPERS_DIR = os.path.join(os.path.dirname(__file__), "..")

# Helper: run a Node.js snippet that imports pptxgenjs-helpers.mjs and returns JSON
def run_node(script):
    result = subprocess.run(
        ["node", "--input-type=module", "-e", script],
        capture_output=True, text=True, cwd=HELPERS_DIR, timeout=10,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node failed: {result.stderr}")
    return json.loads(result.stdout)


# --- loadTheme defaults ---

class TestLoadThemeDefaults:
    """When a theme YAML omits new token sections, loadTheme() fills defaults."""

    def test_typography_defaults(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/default.yaml');
            console.log(JSON.stringify(t.typography));
        """)
        assert theme["title_size"] == 36
        assert theme["heading_size"] == 28
        assert theme["subtitle_size"] == 18
        assert theme["body_size"] == 18
        assert theme["small_size"] == 14
        assert theme["eyebrow_size"] == 8
        assert theme["eyebrow_bold"] == False
        assert theme["eyebrow_char_spacing"] == 6
        assert theme["stat_size"] == 48
        assert theme["stat_bold"] == True
        assert theme["stat_label_size"] == 16
        assert theme["stat_desc_size"] == 13
        assert theme["code_size"] == 14
        assert theme["footer_size"] == 10

    def test_shadow_defaults(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/default.yaml');
            console.log(JSON.stringify(t.shadow));
        """)
        assert theme["blur"] == 4
        assert theme["offset"] == 2
        assert theme["angle"] == 135
        assert theme["color"] == "000000"
        assert theme["opacity"] == 0.12

    def test_eyebrow_defaults(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/default.yaml');
            console.log(JSON.stringify(t.eyebrow));
        """)
        assert theme["show"] == True
        assert theme["dash_width"] == 1.2
        assert theme["dash_height"] == 0.035
        assert theme["label_offset"] == 1.35

    def test_data_colors_defaults(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/default.yaml');
            console.log(JSON.stringify(t.data_colors));
        """)
        assert theme["series_1"] == ""
        assert theme["series_2"] == ""
        assert theme["series_3"] == ""
        assert theme["positive"] == "1AA01A"
        assert theme["negative"] == "D73D2B"
        assert theme["neutral"] == ""

    def test_expanded_color_defaults(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/default.yaml');
            console.log(JSON.stringify({
                code_bg: t.colors.code_bg,
                code_text: t.colors.code_text,
                heading_color: t.colors.heading_color,
                eyebrow_color: t.colors.eyebrow_color,
                stat_color: t.colors.stat_color,
            }));
        """)
        assert theme["code_bg"] == "0D1117"
        assert theme["code_text"] == "58A6FF"
        assert theme["heading_color"] == ""
        assert theme["eyebrow_color"] == ""
        assert theme["stat_color"] == ""


class TestLoadThemeOverrides:
    """When a theme YAML specifies new token values, they override defaults."""

    def test_typography_override(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/instinct.yaml');
            console.log(JSON.stringify(t.typography));
        """)
        # instinct.yaml will set body_size: 16 (design system value)
        assert theme["body_size"] == 16
        # Other values should still be present (from YAML or defaults)
        assert theme["heading_size"] == 28
        assert theme["title_size"] == 36

    def test_shadow_override(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/instinct.yaml');
            console.log(JSON.stringify(t.shadow));
        """)
        # instinct.yaml will set teal-tinted shadow
        assert theme["color"] == "003040"
        assert theme["opacity"] == 0.15
        # Non-overridden values keep defaults
        assert theme["blur"] == 4

    def test_expanded_color_override(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/instinct.yaml');
            console.log(JSON.stringify({
                code_bg: t.colors.code_bg,
                code_text: t.colors.code_text,
            }));
        """)
        assert theme["code_bg"] == "131416"
        assert theme["code_text"] == "00C2DE"


class TestCreateDeckOverrides:
    """createDeck() overrides deep-merge over the loaded theme."""

    def test_typography_override_via_create_deck(self):
        result = run_node("""
            import { createDeck } from './lib/pptxgenjs-helpers.mjs';
            const deck = createDeck('themes/default.yaml', {
                overrides: { typography: { heading_size: 24 } },
            });
            console.log(JSON.stringify({
                heading_size: deck.theme.typography.heading_size,
                title_size: deck.theme.typography.title_size,
            }));
        """)
        assert result["heading_size"] == 24  # overridden
        assert result["title_size"] == 36    # unchanged

    def test_color_override_via_create_deck(self):
        result = run_node("""
            import { createDeck } from './lib/pptxgenjs-helpers.mjs';
            const deck = createDeck('themes/default.yaml', {
                overrides: { colors: { accent: "FF5733" } },
            });
            console.log(JSON.stringify({
                accent: deck.theme.colors.accent,
                background: deck.theme.colors.background,
            }));
        """)
        assert result["accent"] == "FF5733"       # overridden
        assert result["background"] == "1E293B"    # unchanged


class TestBackwardCompatibility:
    """Existing themes without new sections produce identical base token objects."""

    def test_existing_colors_unchanged(self):
        """The 9 original color slots should have the same values as before."""
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/amd.yaml');
            console.log(JSON.stringify(t.colors));
        """)
        assert theme["background"] == "000000"
        assert theme["accent"] == "00C2DE"
        assert theme["text_primary"] == "FFFFFF"
        assert theme["surface"] == "636466"

    def test_existing_fonts_unchanged(self):
        theme = run_node("""
            import { loadTheme } from './lib/pptxgenjs-helpers.mjs';
            const t = loadTheme('themes/amd.yaml');
            console.log(JSON.stringify(t.fonts));
        """)
        assert theme["heading"] == "Arial"
        assert theme["body"] == "Arial"
        assert theme["mono"] == "Consolas"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/test_theme_tokens.py -v --tb=short 2>&1 | head -40`

Expected: FAIL — `theme.typography` is undefined, `theme.shadow` is undefined, etc.

- [ ] **Step 3: Commit test file**

```bash
cd /home/matt/git/shamsway/aippt
git add tests/test_theme_tokens.py
git commit -m "test: add theme token schema v2 tests (red phase)"
```

---

### Task 2: Add TOKEN_DEFAULTS, deepMerge, and expand loadTheme()

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs:77-137` (constants section + loadTheme function)

- [ ] **Step 1: Add TOKEN_DEFAULTS constant and deepMerge utility after the safe-area constants (after line 82)**

Insert after line 82 (`export const SH = 7.5;`):

```javascript
// Token defaults — every new token has a default matching the current hardcoded value.
// Themes override specific values; loadTheme() deep-merges YAML over these.
export const TOKEN_DEFAULTS = {
  typography: {
    title_size: 36, heading_size: 28, subtitle_size: 18,
    body_size: 18, small_size: 14, eyebrow_size: 8,
    eyebrow_bold: false, eyebrow_char_spacing: 6,
    stat_size: 48, stat_bold: true, stat_label_size: 16,
    stat_desc_size: 13, code_size: 14, footer_size: 10,
  },
  data_colors: {
    series_1: "", series_2: "", series_3: "",
    positive: "1AA01A", negative: "D73D2B", neutral: "",
  },
  shadow: {
    blur: 4, offset: 2, angle: 135, color: "000000", opacity: 0.12,
  },
  eyebrow: {
    show: true, dash_width: 1.2, dash_height: 0.035, label_offset: 1.35,
  },
};

function deepMerge(target, source) {
  for (const key of Object.keys(source)) {
    if (
      source[key] !== null &&
      typeof source[key] === "object" &&
      !Array.isArray(source[key]) &&
      typeof target[key] === "object"
    ) {
      deepMerge(target[key], source[key]);
    } else {
      target[key] = source[key];
    }
  }
  return target;
}
```

- [ ] **Step 2: Expand loadTheme() to include new token sections**

In `loadTheme()`, after the existing `theme` object is built (after the `master: parsed.master || null,` line, before `return theme;`), add:

```javascript
  // Expanded color slots (merge into existing colors)
  theme.colors.code_bg = parsed.colors?.code_bg || "0D1117";
  theme.colors.code_text = parsed.colors?.code_text || "58A6FF";
  theme.colors.heading_color = parsed.colors?.heading_color ?? "";
  theme.colors.eyebrow_color = parsed.colors?.eyebrow_color ?? "";
  theme.colors.stat_color = parsed.colors?.stat_color ?? "";

  // New token sections — deep-merge YAML values over defaults
  theme.typography = { ...TOKEN_DEFAULTS.typography, ...parsed.typography };
  theme.data_colors = { ...TOKEN_DEFAULTS.data_colors, ...parsed.data_colors };
  theme.shadow = { ...TOKEN_DEFAULTS.shadow, ...parsed.shadow };
  theme.eyebrow = { ...TOKEN_DEFAULTS.eyebrow, ...parsed.eyebrow };
```

**Important:** Use `??` (nullish coalescing) for `heading_color`, `eyebrow_color`, `stat_color` because `||` would treat `""` as falsy and apply the default, but `""` IS the intended default (meaning "use fallback color"). The parsed YAML would return `""` for explicitly set empty strings.

Wait — actually the fallback default IS `""`. So `parsed.colors?.heading_color ?? ""` works: if the YAML doesn't define it, `parsed.colors?.heading_color` is `undefined`, and `??` falls through to `""`. If the YAML defines it as `"FF0000"`, that value is used. Correct.

- [ ] **Step 3: Run the default and backward-compat tests**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/test_theme_tokens.py::TestLoadThemeDefaults tests/test_theme_tokens.py::TestBackwardCompatibility -v`

Expected: All tests in `TestLoadThemeDefaults` and `TestBackwardCompatibility` PASS.

- [ ] **Step 4: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: add TOKEN_DEFAULTS and expand loadTheme() with new token sections"
```

---

### Task 3: Add overrides to createDeck()

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs` — `createDeck()` function (line ~1212)

- [ ] **Step 1: Add overrides support to createDeck()**

In `createDeck()`, after `const theme = loadTheme(themePath);` and before `const layout = computeLayout(theme);`, add:

```javascript
  if (opts.overrides) {
    deepMerge(theme, opts.overrides);
  }
```

The full function now reads:

```javascript
export function createDeck(themePath, opts = {}) {
  const pptxgen = require("pptxgenjs");
  const theme = loadTheme(themePath);
  if (opts.overrides) {
    deepMerge(theme, opts.overrides);
  }
  const layout = computeLayout(theme);
  const useSlideMaster = opts.useSlideMaster ?? false;
  // ... rest unchanged
```

- [ ] **Step 2: Run the override tests**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/test_theme_tokens.py::TestCreateDeckOverrides -v`

Expected: PASS

- [ ] **Step 3: Run all token tests**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/test_theme_tokens.py -v`

Expected: All tests PASS except `TestLoadThemeOverrides` (instinct.yaml doesn't have the new sections yet — that's Task 10).

- [ ] **Step 4: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: add overrides option to createDeck() for per-deck token control"
```

---

### Task 4: Update cardShadow() to accept theme

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs` — `cardShadow()` (line 161), `_addStepBox()` (line 685), `addCardGrid()` (line 938)

- [ ] **Step 1: Change cardShadow() signature to accept theme**

Replace the current `cardShadow()` function (line 161-166):

```javascript
export function cardShadow(theme) {
  const s = theme?.shadow || TOKEN_DEFAULTS.shadow;
  return {
    type: "outer", blur: s.blur, offset: s.offset,
    angle: s.angle, color: s.color, opacity: s.opacity,
  };
}
```

- [ ] **Step 2: Update _addStepBox() call site (line 685)**

Change `shadow: cardShadow(),` to:

```javascript
    shadow: cardShadow(theme),
```

- [ ] **Step 3: Update addCardGrid() call site (line 938)**

Change `shadow: cardShadow(),` to:

```javascript
      shadow: cardShadow(theme),
```

- [ ] **Step 4: Verify no other cardShadow() callers were missed**

Run: `grep -n "cardShadow" lib/pptxgenjs-helpers.mjs`

Expected: 3 lines — the function definition plus the two updated call sites.

- [ ] **Step 5: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: cardShadow() reads from theme.shadow tokens"
```

---

### Task 5: Update addEyebrowText() to read theme.eyebrow

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs` — `addEyebrowText()` (line 231-247)

- [ ] **Step 1: Replace addEyebrowText() implementation**

Replace the current function (lines 231-247) with:

```javascript
export function addEyebrowText(slide, label, themeOrDeck) {
  const theme = themeOrDeck.theme || themeOrDeck;
  const pptx = themeOrDeck.pptx || null;
  const M = theme.slide.margin;
  const C = theme.colors;
  const EB = theme.eyebrow;
  const T = theme.typography;
  const eyebrowColor = C.eyebrow_color || C.accent;
  if (pptx && EB.show) {
    slide.addShape(pptx.ShapeType.rect, {
      x: M, y: 0.22, w: EB.dash_width, h: EB.dash_height,
      fill: { color: eyebrowColor },
    });
  }
  slide.addText(label.toUpperCase(), {
    x: M + EB.label_offset, y: 0.16, w: 8.0, h: 0.14,
    fontSize: T.eyebrow_size, fontFace: theme.fonts.body,
    color: eyebrowColor, charSpacing: T.eyebrow_char_spacing,
    bold: T.eyebrow_bold,
  });
}
```

Key changes:
- Accent dash dimensions read from `EB.dash_width` and `EB.dash_height`
- Dash is conditional on `EB.show` (themes can disable the dash)
- Text offset reads from `EB.label_offset`
- fontSize, charSpacing, bold read from `T.eyebrow_size`, `T.eyebrow_char_spacing`, `T.eyebrow_bold`
- Color uses `C.eyebrow_color || C.accent` fallback

- [ ] **Step 2: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: addEyebrowText() reads from theme.eyebrow and theme.typography tokens"
```

---

### Task 6: Update addCodeSlide() colors

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs` — `addCodeSlide()` (lines 1063-1076)

- [ ] **Step 1: Replace hardcoded hex colors with theme token references**

In `addCodeSlide()`, change the code block background fill (line ~1065):

```javascript
    fill: { color: C.code_bg },
```

Change the code text color (line ~1076):

```javascript
    color: C.code_text,
```

And change the code fontSize (same text object):

```javascript
    fontSize: T.code_size, fontFace: theme.fonts.mono,
```

For this to work, add `const T = theme.typography;` at the top of the function, alongside the existing destructuring. The full function top becomes:

```javascript
export function addCodeSlide(deck, title, code, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
```

- [ ] **Step 2: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: addCodeSlide() reads code_bg, code_text, code_size from theme"
```

---

### Task 7: Update semantic color fallbacks and stat tokens

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs` — heading color in all content slide builders, stat colors in `addStatCallout()`

This task updates color references to use the semantic fallback pattern (`theme.colors.X || fallback`).

- [ ] **Step 1: Update addStatCallout() for stat tokens**

In `addStatCallout()` (around line 995-1038), add `const T = theme.typography;` at the top and update:

Title heading (line ~998):
```javascript
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
```

Stat value (line ~1012):
```javascript
    fontSize: T.stat_size, fontFace: theme.fonts.heading,
    color: C.stat_color || C.accent, bold: T.stat_bold,
```

Stat label (line ~1019):
```javascript
    fontSize: T.stat_label_size, fontFace: theme.fonts.body,
```

Stat description (line ~1027):
```javascript
    fontSize: T.stat_desc_size, fontFace: theme.fonts.body,
```

- [ ] **Step 2: Update heading color across all content slide builders**

In every slide builder function that has a title with `fontSize: 28` and `color: C.text_primary`, change the color to:

```javascript
    color: C.heading_color || C.text_primary,
```

Functions to update (heading text object only):
- `addBulletSlide()` — line ~383
- `addImageSlide()` — line ~462
- `addImageBulletsSlide()` — line ~524
- `addIconRowsSlide()` — line ~631
- `addProcessFlow()` — line ~740
- `addTwoColumn()` — line ~832
- `addCardGrid()` — line ~928 (the main title, not card titles)
- `addStatCallout()` — line ~998
- `addCodeSlide()` — line ~1059

- [ ] **Step 3: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: semantic color fallbacks for heading, stat, and eyebrow colors"
```

---

### Task 8: Update typography fontSize references across all builders

**Files:**
- Modify: `lib/pptxgenjs-helpers.mjs` — fontSize replacements in all slide builders

This is the main sweep. Each function needs `const T = theme.typography;` added (if not already present) and its heading `fontSize: 28` replaced with `T.heading_size`.

- [ ] **Step 1: Add T = theme.typography to each builder and replace heading fontSize**

For each function listed below, add `const T = theme.typography;` after the existing `const C = theme.colors;` line, then replace `fontSize: 28` with `fontSize: T.heading_size` in the title text object.

Functions and their heading fontSize locations:

| Function | Title fontSize line | Current | New |
|----------|-------------------|---------|-----|
| `addBulletSlide()` | ~383 | `fontSize: 28` | `fontSize: T.heading_size` |
| `addImageSlide()` | ~462 | `fontSize: 28` | `fontSize: T.heading_size` |
| `addImageBulletsSlide()` | ~524 | `fontSize: 28` | `fontSize: T.heading_size` |
| `addIconRowsSlide()` | ~631 | `fontSize: 28` | `fontSize: T.heading_size` |
| `addProcessFlow()` | ~740 | `fontSize: 28` | `fontSize: T.heading_size` |
| `addTwoColumn()` | ~832 | `fontSize: 28` | `fontSize: T.heading_size` |
| `addCardGrid()` | ~928 (main title) | `fontSize: 28` | `fontSize: T.heading_size` |

(addStatCallout and addCodeSlide were already handled in Tasks 6-7.)

- [ ] **Step 2: Update addTitleSlide() typography**

In `addTitleSlide()`:
- Add `const T = theme.typography;` after `const C = theme.colors;`
- Title (line ~315): `fontSize: T.title_size`
- Subtitle (line ~327): `fontSize: T.subtitle_size`

- [ ] **Step 3: Update addFooter() typography**

In `addFooter()` (line ~269): change `fontSize: 10` to `fontSize: theme.typography.footer_size`

(No `T` shorthand needed here since `addFooter` receives `theme` directly, not `deck`.)

- [ ] **Step 4: Verify all 28 → T.heading_size replacements**

Run: `grep -n "fontSize: 28" lib/pptxgenjs-helpers.mjs`

Expected: Only hits in non-tokenized functions (`addProcessFlow` arrows at lines ~762, ~786, ~801 — these are layout mechanics, not headings, so they stay hardcoded).

- [ ] **Step 5: Verify no hardcoded fontSize: 36, 48, 10, 8, 14 (for code) remain in tokenized contexts**

Run: `grep -n "fontSize:" lib/pptxgenjs-helpers.mjs | grep -v "T\.\|theme\.typography"`

Review output — remaining hardcoded values should only be in:
- Adaptive bullet sizing (22/24/20/22/18/20/16/18) — layout mechanics
- Step box internals (24/16/13/14) — layout mechanics
- Two-column adaptive (17/16/15/14/13) — layout mechanics
- Card grid card body/title (18/14) — layout mechanics
- Icon row label/desc (20/14) — layout mechanics
- Section divider (96/12/42) — layout mechanics
- Closing slide (48) — layout mechanics
- Process flow arrows (28/24) — layout mechanics
- Image slide placeholder (14/12) — layout mechanics

- [ ] **Step 6: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-helpers.mjs
git commit -m "feat: replace hardcoded fontSize values with theme.typography tokens in all builders"
```

---

### Task 9: Update masters footer_size

**Files:**
- Modify: `lib/pptxgenjs-masters.mjs:87`

- [ ] **Step 1: Replace hardcoded fontSize in slide number**

At line 87 in `lib/pptxgenjs-masters.mjs`, change:

```javascript
      fontSize: 10, fontFace: theme.fonts.body,
```

to:

```javascript
      fontSize: theme.typography.footer_size, fontFace: theme.fonts.body,
```

- [ ] **Step 2: Verify no other hardcoded fontSize values in masters**

Run: `grep -n "fontSize" lib/pptxgenjs-masters.mjs`

Expected: Only the one instance, now reading from theme.typography.

- [ ] **Step 3: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add lib/pptxgenjs-masters.mjs
git commit -m "feat: master slide number reads fontSize from theme.typography.footer_size"
```

---

### Task 10: Update theme YAML files

**Files:**
- Modify: `themes/default.yaml`
- Modify: `themes/amd.yaml`
- Modify: `themes/instinct.yaml`

- [ ] **Step 1: Add token sections to default.yaml**

Append to the end of `themes/default.yaml`:

```yaml

typography:
  title_size: 36
  heading_size: 28
  subtitle_size: 18
  body_size: 18
  small_size: 14
  eyebrow_size: 8
  eyebrow_bold: false
  eyebrow_char_spacing: 6
  stat_size: 48
  stat_bold: true
  stat_label_size: 16
  stat_desc_size: 13
  code_size: 14
  footer_size: 10

data_colors:
  series_1: ""
  series_2: ""
  series_3: ""
  positive: "1AA01A"
  negative: "D73D2B"
  neutral: ""

shadow:
  blur: 4
  offset: 2
  angle: 135
  color: "000000"
  opacity: 0.12

eyebrow:
  show: true
  dash_width: 1.2
  dash_height: 0.035
  label_offset: 1.35
```

- [ ] **Step 2: Add token sections to amd.yaml**

Append to the end of `themes/amd.yaml` (same values — AMD theme uses the same defaults as the hardcoded values):

```yaml

typography:
  title_size: 36
  heading_size: 28
  subtitle_size: 18
  body_size: 18
  small_size: 14
  eyebrow_size: 8
  eyebrow_bold: false
  eyebrow_char_spacing: 6
  stat_size: 48
  stat_bold: true
  stat_label_size: 16
  stat_desc_size: 13
  code_size: 14
  footer_size: 10

data_colors:
  series_1: ""
  series_2: ""
  series_3: ""
  positive: "1AA01A"
  negative: "D73D2B"
  neutral: ""

shadow:
  blur: 4
  offset: 2
  angle: 135
  color: "000000"
  opacity: 0.12

eyebrow:
  show: true
  dash_width: 1.2
  dash_height: 0.035
  label_offset: 1.35
```

- [ ] **Step 3: Add token sections to instinct.yaml with design system values**

Append to the end of `themes/instinct.yaml`:

```yaml

typography:
  title_size: 36
  heading_size: 28
  subtitle_size: 18
  body_size: 16
  small_size: 14
  eyebrow_size: 8
  eyebrow_bold: false
  eyebrow_char_spacing: 6
  stat_size: 48
  stat_bold: true
  stat_label_size: 16
  stat_desc_size: 13
  code_size: 14
  footer_size: 10

colors:
  code_bg: "131416"
  code_text: "00C2DE"
  stat_color: "00C2DE"

data_colors:
  series_1: "00C2DE"
  series_2: "F26522"
  series_3: "27272a"
  positive: "1AA01A"
  negative: "D73D2B"
  neutral: "b4b9bc"

shadow:
  blur: 4
  offset: 2
  angle: 135
  color: "003040"
  opacity: 0.15

eyebrow:
  show: true
  dash_width: 1.2
  dash_height: 0.035
  label_offset: 1.35
```

**Important for instinct.yaml:** The expanded `colors:` section (code_bg, code_text, stat_color) must be appended to the existing `colors:` block, NOT added as a second `colors:` key. YAML does not allow duplicate top-level keys — a second `colors:` would silently overwrite the first. Merge these new keys into the existing `colors:` section in the file.

- [ ] **Step 4: Run the override tests**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/test_theme_tokens.py::TestLoadThemeOverrides -v`

Expected: All `TestLoadThemeOverrides` tests PASS (instinct.yaml now has the new sections).

- [ ] **Step 5: Run all token tests**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/test_theme_tokens.py -v`

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add themes/default.yaml themes/amd.yaml themes/instinct.yaml
git commit -m "feat: add token schema v2 sections to all three bundled themes"
```

---

### Task 11: Visual regression test and full verification

**Files:**
- Uses existing example scripts in `examples/`

- [ ] **Step 1: Find an example deck script that exercises multiple slide types**

Run: `ls examples/*.mjs | head -5`

Pick a script that uses title, bullet, image, stat, code, and card slides. The `slides-as-code-design-master` example is a good candidate.

- [ ] **Step 2: Generate a reference deck with the default theme**

Run: `cd /home/matt/git/shamsway/aippt && node examples/slides-as-code-design-master/slides-as-code-design-amd-master.mjs`

Inspect the output PPTX manually — verify slides look correct (headings at 28pt, stats at 48pt, footers at 10pt, eyebrow at 8pt with teal dash).

- [ ] **Step 3: Generate a deck with instinct theme (if an instinct example exists)**

Run: `ls examples/*instinct*` to find one. If none exists, generate the same deck with `themes/instinct.yaml` by modifying the theme path temporarily.

Verify: code block should use `131416` background (design system dark) instead of `0D1117` (GitHub dark). Shadow should be teal-tinted.

- [ ] **Step 4: Test createDeck overrides end-to-end**

Create a one-off test script:

```bash
cd /home/matt/git/shamsway/aippt
node --input-type=module -e "
import { createDeck, addBulletSlide, addStatCallout } from './lib/pptxgenjs-helpers.mjs';
const deck = createDeck('themes/default.yaml', {
  overrides: { typography: { heading_size: 24, stat_size: 56 } },
});
addBulletSlide(deck, 'Override Test', ['Heading should be 24pt'], 1, 'test notes');
addStatCallout(deck, 'Stats', [{ value: '99%', label: 'Accuracy' }], 2, 'test');
await deck.save('test-overrides.pptx');
console.log('Override deck saved');
"
```

Open `test-overrides.pptx` and verify heading is 24pt and stat number is 56pt.

- [ ] **Step 5: Clean up test artifacts**

```bash
rm -f test-overrides.pptx
```

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `cd /home/matt/git/shamsway/aippt && python3 -m pytest tests/ -v --tb=short 2>&1 | tail -20`

Expected: All tests PASS, no regressions.

---

### Task 12: Update CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add changelog entry at the top of the Unreleased section**

Add under the appropriate heading (or create `## [Unreleased]` if needed):

```markdown
### Added
- Theme token schema v2: typography scale (14 tokens), data visualization colors (6 tokens), shadow configuration (5 tokens), and eyebrow component tokens (4 tokens) in theme YAML
- `createDeck()` accepts `overrides` option for per-deck token adjustments by agents
- Expanded color slots: `code_bg`, `code_text`, `heading_color`, `eyebrow_color`, `stat_color`

### Changed
- ~40 hardcoded design values in pptxgenjs helpers now read from theme tokens
- `cardShadow()` now accepts `theme` parameter and reads from `theme.shadow.*`
- All three bundled themes updated with explicit token values (no visual change for `default` and `amd`; `instinct` gets design-system-aligned values)
```

- [ ] **Step 2: Commit**

```bash
cd /home/matt/git/shamsway/aippt
git add CHANGELOG.md
git commit -m "docs: add theme token schema v2 changelog entry"
```

---

## Execution Notes

- **Tasks 1-3** are the foundation (test + loadTheme + createDeck). Must run sequentially.
- **Tasks 4-9** are the builder updates. They all depend on Task 2 (TOKEN_DEFAULTS exists) but are independent of each other — they can run in parallel via subagent dispatch.
- **Task 10** (theme YAMLs) depends on Task 2 (loadTheme can parse the new sections).
- **Task 11** (visual regression) depends on all code tasks (4-10) being complete.
- **Task 12** (changelog) is independent.

### Parallelization Map

```
Task 1 → Task 2 → Task 3
                ↘
                  Task 4 ─┐
                  Task 5 ─┤
                  Task 6 ─┤
                  Task 7 ─┤ → Task 11 → Task 12
                  Task 8 ─┤
                  Task 9 ─┤
                  Task 10 ┘
```

Tasks 4-10 can be dispatched as parallel subagents since they modify different functions/files (except Tasks 4-9 all touch `pptxgenjs-helpers.mjs` — if using subagents, they must work on separate sections to avoid merge conflicts, or run sequentially).

**Recommended execution:** Tasks 4-9 sequentially in a single session (they're all in the same file), Task 10 can parallel with 4-9 since it touches different files.
