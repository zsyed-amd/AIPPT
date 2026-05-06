# Design Spec: Theme Token Schema v2

**Date:** 2026-05-06
**Source PRD:** `.local-docs/plans/2026-05-06-theme-token-schema-v2.md`
**Status:** Approved

---

## Goal

Expand the pptxgenjs theme YAML schema from 15 fields to ~49 fields (15 existing + 34 new tokens). Replace ~40 hardcoded design decisions in `pptxgenjs-helpers.mjs` with theme-driven values. Add a `createDeck()` overrides mechanism for per-deck agent control.

## Architecture

### Token Resolution Order

```
loadTheme() defaults → Theme YAML values → createDeck() overrides → per-slide function args
```

Each layer deep-merges over the previous. A theme with only `colors:` and `fonts:` still produces a complete deck because `loadTheme()` fills every token with a default extracted from the current hardcoded values.

### What Gets Tokenized

**Design decisions** (would a brand designer want to control it?) become tokens:
- Font sizes for headings, body, stats, eyebrow, code, footer
- Shadow treatment (blur, offset, angle, color, opacity)
- Eyebrow component geometry (dash width/height, label offset, show/hide)
- Semantic color overrides (code block, heading, stat, eyebrow colors)
- Data visualization palette (series colors, positive/negative/neutral)

**Layout mechanics** (only a pptxgenjs engineer would touch) stay hardcoded:
- Icon circle positions, card text offsets, process flow arrow sizing
- Adaptive bullet sizing profiles (deferred to nice-to-have)
- Two-column adaptive sizing thresholds
- Content area Y offset, footer Y position

### Files Modified

| File | Change |
|------|--------|
| `lib/pptxgenjs-helpers.mjs` | `loadTheme()` defaults + deep-merge; `createDeck()` overrides; slide builders read tokens |
| `lib/pptxgenjs-masters.mjs` | Master slide number fontSize reads `theme.typography.footer_size` |
| `themes/default.yaml` | Add new token sections (values = current hardcoded defaults, no visual change) |
| `themes/amd.yaml` | Add new token sections (values = current hardcoded defaults, no visual change) |
| `themes/instinct.yaml` | Add new token sections with Instinct design system values |

---

## Token Schema

### Typography (14 tokens)

```yaml
typography:
  title_size: 36          # Title slide main heading
  heading_size: 28         # Content slide heading
  subtitle_size: 18        # Title slide subtitle
  body_size: 18            # Default body text (non-adaptive contexts)
  small_size: 14           # Captions, footnotes, descriptions
  eyebrow_size: 8          # Uppercase section labels
  eyebrow_bold: false      # Eyebrow weight
  eyebrow_char_spacing: 6  # pptxgenjs charSpacing units
  stat_size: 48            # Hero numbers on stat slides
  stat_bold: true          # Stat number weight
  stat_label_size: 16      # Stat callout label text
  stat_desc_size: 13       # Stat callout description text
  code_size: 14            # Code block monospace text
  footer_size: 10          # Slide number text
```

`body_size` applies to non-adaptive contexts. `addBulletSlide()` uses its own adaptive sizing table (22/20/18/16 based on item count); that system is separate and deferred to the `bullet_profiles` nice-to-have.

### Colors — Expanded (5 new tokens)

```yaml
colors:
  # ... existing 9 colors unchanged ...
  code_bg: "0D1117"        # Code block background
  code_text: "58A6FF"      # Code block text
  heading_color: ""        # Slide heading color (fallback: text_primary)
  eyebrow_color: ""        # Eyebrow label color (fallback: accent)
  stat_color: ""           # Stat number color (fallback: accent)
```

Empty string = fall back to the named default. `table_header_bg` and `table_header_text` are deferred until a table slide function exists.

### Data Visualization Colors (6 tokens)

```yaml
data_colors:
  series_1: ""             # Primary data series (fallback: accent)
  series_2: ""             # Secondary series (fallback: accent_alt)
  series_3: ""             # Tertiary series (fallback: surface)
  positive: "1AA01A"       # Above-parity / good
  negative: "D73D2B"       # Below-parity / bad
  neutral: ""              # Baseline / parity (fallback: text_secondary)
```

### Shadow (5 tokens)

```yaml
shadow:
  blur: 4
  offset: 2
  angle: 135
  color: "000000"
  opacity: 0.12
```

### Eyebrow Component (4 tokens)

```yaml
eyebrow:
  show: true               # Whether to render eyebrow chrome
  dash_width: 1.2          # Accent dash width (inches)
  dash_height: 0.035       # Accent dash height (inches)
  label_offset: 1.35       # Horizontal offset for label text (inches)
```

### Total: 34 new tokens

| Category | Count |
|----------|-------|
| `typography` | 14 |
| `colors` (expanded) | 5 |
| `data_colors` | 6 |
| `shadow` | 5 |
| `eyebrow` | 4 |
| **Total** | **34** |

---

## Implementation Details

### Deep Merge in `loadTheme()`

Add a `TOKEN_DEFAULTS` constant with all new token defaults. After parsing the YAML, deep-merge each new section:

```javascript
const TOKEN_DEFAULTS = {
  typography: { title_size: 36, heading_size: 28, ... },
  data_colors: { series_1: "", series_2: "", ... },
  shadow: { blur: 4, offset: 2, ... },
  eyebrow: { show: true, dash_width: 1.2, ... },
};
```

For each section, merge parsed values over defaults:
```javascript
theme.typography = { ...TOKEN_DEFAULTS.typography, ...parsed.typography };
```

The expanded color slots merge into the existing `theme.colors` object with fallback logic:
```javascript
theme.colors.code_bg = parsed.colors?.code_bg || "0D1117";
theme.colors.code_text = parsed.colors?.code_text || "58A6FF";
theme.colors.heading_color = parsed.colors?.heading_color || "";
theme.colors.eyebrow_color = parsed.colors?.eyebrow_color || "";
theme.colors.stat_color = parsed.colors?.stat_color || "";
```

### `createDeck()` Overrides

Add `opts.overrides` support with a simple deep-merge utility:

```javascript
export function createDeck(themePath, opts = {}) {
  const theme = loadTheme(themePath);
  if (opts.overrides) {
    deepMerge(theme, opts.overrides);
  }
  // ... rest unchanged
}
```

The `deepMerge` utility handles one level of nesting (sufficient for all token sections).

### `cardShadow()` Signature Change

Change from `cardShadow()` (no args) to `cardShadow(theme)`:

```javascript
export function cardShadow(theme) {
  const s = theme?.shadow || TOKEN_DEFAULTS.shadow;
  return { type: "outer", blur: s.blur, offset: s.offset, angle: s.angle, color: s.color, opacity: s.opacity };
}
```

All callers updated to pass `theme`. Falls back to defaults if no theme provided for safety.

### Semantic Color Fallbacks

In slide builders, use the pattern:
```javascript
const headingColor = C.heading_color || C.text_primary;
const eyebrowColor = C.eyebrow_color || C.accent;
const statColor = C.stat_color || C.accent;
```

### `addEyebrowText()` Update

Read from `theme.eyebrow.*` instead of hardcoded values. When `theme.eyebrow.show === false`, skip the accent dash (text-only eyebrow or no eyebrow at all, depending on the theme).

---

## Theme Updates

### `default.yaml` and `amd.yaml`

Add all new token sections with values matching current hardcoded defaults. No visual change.

### `instinct.yaml`

Add tokens with Instinct design system values from `DESIGN.md`:

```yaml
typography:
  title_size: 36
  heading_size: 28
  subtitle_size: 18
  body_size: 16           # Design system: pptx-body = 16pt (vs default 18)
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
  code_bg: "131416"        # Design system background color
  code_text: "00C2DE"      # Design system primary (teal)

data_colors:
  series_1: "00C2DE"       # AMD teal
  series_2: "F26522"       # AMD orange (accent_alt)
  series_3: "27272a"       # Surface
  positive: "1AA01A"
  negative: "D73D2B"
  neutral: "b4b9bc"        # text_secondary

shadow:
  blur: 4
  offset: 2
  angle: 135
  color: "003040"          # Teal-tinted shadow
  opacity: 0.15

eyebrow:
  show: true
  dash_width: 1.2
  dash_height: 0.035
  label_offset: 1.35
```

---

## Backward Compatibility

- All defaults extracted directly from current hardcoded values — no rounding
- Existing theme YAMLs work unchanged (new sections are optional)
- `cardShadow(theme)` falls back to defaults if theme is undefined
- Semantic color fallbacks use `||` so empty string correctly falls through

## Testing

1. **Unit:** `loadTheme()` returns all defaults when YAML omits new sections
2. **Unit:** Explicit YAML values override defaults
3. **Unit:** `createDeck()` overrides merge correctly over loaded theme
4. **Unit:** Existing themes produce identical token objects (backward compat)
5. **Visual:** Render reference decks before/after, compare output
6. **Manual:** Generate with `instinct.yaml` overrides to verify stat_size, heading_size, code colors
