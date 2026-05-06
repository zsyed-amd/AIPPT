/**
 * pptxgenjs-helpers.mjs — reusable slide builder library for pptxgenjs engine.
 *
 * Usage from output/ scripts:
 *   import { createDeck, addTitleSlide, addBulletSlide, ... } from '../lib/pptxgenjs-helpers.mjs';
 *
 * All slide builders accept a `deck` object from createDeck() which bundles
 * pptx, theme, and layout so callers don't juggle three args.
 */

import { readFileSync, existsSync, statSync } from "fs";
import { createRequire } from "module";
import { defineMasters, masterNameFor } from './pptxgenjs-masters.mjs';

const require = createRequire(import.meta.url);

// YAML parsing — use js-yaml if available, fall back to simple parser
let yamlParse;
try {
  const jsyaml = require("js-yaml");
  yamlParse = (str) => jsyaml.load(str);
} catch {
  // Minimal YAML parser for theme files (handles flat keys, nested objects, quoted strings)
  yamlParse = (str) => {
    const result = {};
    const lines = str.split("\n");
    let currentSection = null;

    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, "");
      // Skip comments and blank lines
      if (/^\s*#/.test(line) || /^\s*$/.test(line)) continue;

      const indent = line.search(/\S/);
      const content = line.trim();

      // Key: value line
      const kvMatch = content.match(/^(\w[\w_]*):\s*(.*)/);
      if (!kvMatch) continue;

      const key = kvMatch[1];
      let value = kvMatch[2].trim();

      if (indent === 0) {
        if (value === "" || value === "|") {
          // Section header
          currentSection = {};
          result[key] = currentSection;
        } else {
          result[key] = parseValue(value);
          currentSection = null;
        }
      } else if (currentSection !== null) {
        currentSection[key] = parseValue(value);
      }
    }
    return result;
  };

  function parseValue(v) {
    // Remove inline comments
    v = v.replace(/\s+#.*$/, "");
    // Quoted string
    if (/^"(.*)"$/.test(v)) return v.slice(1, -1);
    if (/^'(.*)'$/.test(v)) return v.slice(1, -1);
    // Boolean
    if (v === "true") return true;
    if (v === "false") return false;
    // Number
    if (/^-?\d+(\.\d+)?$/.test(v)) return parseFloat(v);
    // Plain string
    return v;
  }
}


// ═══════════════════════════════════════════════════════════════
// Safe-area constants (LAYOUT_WIDE = 13.33" × 7.5")
// ═══════════════════════════════════════════════════════════════

export const SW = 13.33;
export const SH = 7.5;

// Token defaults — every new token has a default matching the current hardcoded value.
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


// ═══════════════════════════════════════════════════════════════
// Theme & Config
// ═══════════════════════════════════════════════════════════════

/**
 * Load a theme YAML file and return a structured config object.
 * @param {string} yamlPath - Path to themes/*.yaml
 * @returns {{ colors, fonts, logo, slide, footer, name, description }}
 */
export function loadTheme(yamlPath) {
  const raw = readFileSync(yamlPath, "utf8");
  const parsed = yamlParse(raw);

  const theme = {
    name: parsed.name || "",
    description: parsed.description || "",
    colors: {
      background: parsed.colors?.background || "000000",
      background_alt: parsed.colors?.background_alt || parsed.colors?.background || "000000",
      surface: parsed.colors?.surface || "333333",
      text_primary: parsed.colors?.text_primary || "FFFFFF",
      text_secondary: parsed.colors?.text_secondary || "999999",
      text_body: parsed.colors?.text_body || "CCCCCC",
      accent: parsed.colors?.accent || "3B82F6",
      accent_alt: parsed.colors?.accent_alt || "10B981",
      warning: parsed.colors?.warning || "EF4444",
    },
    fonts: {
      heading: parsed.fonts?.heading || "Arial",
      body: parsed.fonts?.body || "Arial",
      mono: parsed.fonts?.mono || "Consolas",
    },
    logo: {
      path: parsed.logo?.path || "",
      width: parsed.logo?.width_inches || 0,
      height: parsed.logo?.height_inches || 0,
      x: parsed.logo?.x_inches || 0,
      y: parsed.logo?.y_inches || 0,
    },
    slide: {
      layout: parsed.slide?.layout || "LAYOUT_WIDE",
      margin: parsed.slide?.margin_inches || 0.5,
    },
    footer: {
      show: parsed.footer?.show !== false,
      text: parsed.footer?.text || "",
      showSlideNumbers: parsed.footer?.show_slide_numbers !== false,
    },
    master: parsed.master || null,
  };

  // Expanded color slots
  theme.colors.code_bg = parsed.colors?.code_bg || "0D1117";
  theme.colors.code_text = parsed.colors?.code_text || "58A6FF";
  theme.colors.heading_color = parsed.colors?.heading_color ?? "";
  theme.colors.eyebrow_color = parsed.colors?.eyebrow_color ?? "";
  theme.colors.stat_color = parsed.colors?.stat_color ?? "";

  // New token sections
  theme.typography = { ...TOKEN_DEFAULTS.typography, ...parsed.typography };
  theme.data_colors = { ...TOKEN_DEFAULTS.data_colors, ...parsed.data_colors };
  theme.shadow = { ...TOKEN_DEFAULTS.shadow, ...parsed.shadow };
  theme.eyebrow = { ...TOKEN_DEFAULTS.eyebrow, ...parsed.eyebrow };

  return theme;
}


/**
 * Compute layout geometry from a theme.
 * @param {{ slide: { margin: number } }} theme
 * @returns {{ M, CONTENT_W, CONTENT_Y, FOOTER_Y, CONTENT_H, RIGHT_EDGE }}
 */
export function computeLayout(theme) {
  const M = theme.slide.margin;
  const CONTENT_W = SW - 2 * M;
  const CONTENT_Y = 1.2;
  const FOOTER_Y = SH - 0.6;
  const CONTENT_H = FOOTER_Y - CONTENT_Y;
  const RIGHT_EDGE = SW - M;
  return { M, CONTENT_W, CONTENT_Y, FOOTER_Y, CONTENT_H, RIGHT_EDGE };
}


// ═══════════════════════════════════════════════════════════════
// Infrastructure
// ═══════════════════════════════════════════════════════════════

/** Fresh shadow object factory — never reuse shadow objects in pptxgenjs. */
export function cardShadow(theme) {
  const s = theme?.shadow || TOKEN_DEFAULTS.shadow;
  return {
    type: "outer", blur: s.blur, offset: s.offset,
    angle: s.angle, color: s.color, opacity: s.opacity,
  };
}


/**
 * Render a react-icons component to SVG string.
 * @param {Function} IconComponent - React icon component
 * @param {number} size - Icon size in pixels
 * @param {string} color - Hex color without #
 * @returns {string} SVG markup
 */
export function renderIconSvg(IconComponent, size = 256, color = "FFFFFF") {
  const React = require("react");
  const ReactDOMServer = require("react-dom/server");
  const el = React.createElement(IconComponent, { size, color: `#${color}` });
  return ReactDOMServer.renderToStaticMarkup(el);
}


/**
 * Convert SVG string to base64 PNG data URI via sharp.
 * @param {string} svgString - SVG markup
 * @param {number} size - Output size in pixels
 * @returns {Promise<string>} base64 data URI for pptxgenjs addImage
 */
export async function iconToBase64(svgString, size = 256) {
  const sharp = require("sharp");
  const buf = Buffer.from(svgString);
  const png = await sharp(buf, { density: 300 })
    .resize(size, size)
    .png()
    .toBuffer();
  return `image/png;base64,${png.toString("base64")}`;
}


/**
 * Pre-render a map of named icons to base64 PNGs.
 * @param {Object} iconMap - { name: { component, color } }
 * @returns {Promise<Object>} { name: base64DataUri }
 */
export async function preRenderIcons(iconMap) {
  const result = {};
  for (const [name, { component, color }] of Object.entries(iconMap)) {
    const svg = renderIconSvg(component, 256, color || "FFFFFF");
    result[name] = await iconToBase64(svg);
  }
  return result;
}


// ═══════════════════════════════════════════════════════════════
// Footer
// ═══════════════════════════════════════════════════════════════

/**
 * Add Instinct-style eyebrow label: short teal dash + uppercase spaced label text.
 * Self-contained — draws both the accent dash and the label text.
 * Use sparingly: eyebrows distract from the title on standard content slides.
 * Best suited for section dividers or slides without a prominent heading.
 *
 * Accepts either (slide, label, theme) [legacy] or (slide, label, deck).
 * @param {Object} slide - pptxgenjs slide
 * @param {string} label - Section label (e.g. "PLATFORM OVERVIEW")
 * @param {Object} themeOrDeck - theme config or deck object
 */
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


/**
 * Add footer (slide number + optional logo) to a slide.
 * @param {Object} slide - pptxgenjs slide
 * @param {number} slideNum - Slide number to display
 * @param {{ colors, fonts, logo }} theme - Theme config
 * @param {{ suppressLogo?, suppressNumber? }} opts
 */
export function addFooter(slide, slideNum, theme, opts = {}) {
  const { suppressLogo = false, suppressNumber = false, deck } = opts;
  if (deck?.useSlideMaster) {
    console.debug('addFooter: skipped — deck uses slide masters');
    return;
  }
  const C = theme.colors;
  const FONT_BODY = theme.fonts.body;

  if (!suppressNumber) {
    slide.addText(`${slideNum}`, {
      x: 0.2, y: SH - 0.45, w: 0.5, h: 0.3,
      fontSize: theme.typography.footer_size, fontFace: FONT_BODY,
      color: C.text_primary,
    });
  }

  if (!suppressLogo && theme.logo.path && existsSync(theme.logo.path)) {
    slide.addImage({
      path: theme.logo.path,
      x: theme.logo.x, y: theme.logo.y,
      w: theme.logo.width, h: theme.logo.height,
    });
  }
}


// ═══════════════════════════════════════════════════════════════
// Slide Builders
// ═══════════════════════════════════════════════════════════════

// All slide builders accept a `deck` object: { pptx, theme, layout }

/**
 * Add a title slide (AMD style: logo left, title right, accent bar).
 */
export function addTitleSlide(deck, title, subtitle, slideNum) {
  const { pptx, theme, layout } = deck;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('title') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  // Logo image (large, left side)
  const logoJpg = theme.logo.path ? theme.logo.path.replace("-wordmark.png", "-logo.jpg") : "";
  if (logoJpg && existsSync(logoJpg)) {
    slide.addImage({
      path: logoJpg,
      x: 0.8, y: 1.5, w: 4.5, h: 4.5,
    });
  }

  slide.addText(title, {
    x: 5.8, y: 2.0, w: 6.5, h: 1.4,
    fontSize: T.title_size, fontFace: theme.fonts.heading,
    color: C.text_primary, bold: true,
  });

  slide.addShape(pptx.ShapeType.rect, {
    x: 5.8, y: 3.5, w: 2.0, h: 0.06,
    fill: { color: C.accent },
  });

  if (subtitle) {
    slide.addText(subtitle, {
      x: 5.8, y: 3.7, w: 6.5, h: 0.8,
      fontSize: T.subtitle_size, fontFace: theme.fonts.body,
      color: C.text_secondary,
    });
  }

  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


// --- Bullet slide internals ---

function _pushBulletItem(textItems, text, leadSize, bodySize, spacing, C) {
  const match = text.match(/^\*\*(.+?)\*\*\s*[—–\-]\s*(.*)/);
  if (match) {
    textItems.push(
      { text: match[1] + " \u2014 ", options: { bold: true, fontSize: leadSize, color: C.text_primary, breakLine: false } },
      { text: match[2], options: { fontSize: bodySize, color: C.text_body, breakLine: true, paraSpaceAfter: spacing } }
    );
  } else {
    const match2 = text.match(/^\*\*(.+?)\*\*\s*(.*)/);
    if (match2) {
      textItems.push(
        { text: match2[1] + " ", options: { bold: true, fontSize: leadSize, color: C.text_primary, breakLine: false } },
        { text: match2[2], options: { fontSize: bodySize, color: C.text_body, breakLine: true, paraSpaceAfter: spacing } }
      );
    } else {
      textItems.push(
        { text, options: { fontSize: bodySize, color: C.text_body, bullet: true, breakLine: true, paraSpaceAfter: spacing } }
      );
    }
  }
}


/**
 * Add a bullet slide with adaptive font sizing.
 * Bullets support bold lead-in: "**Bold** — rest"
 * Bullets can also be {text, subs: [...]} objects for sub-bullets.
 */
export function addBulletSlide(deck, title, bullets, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('bullet') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  // Adaptive font size + spacing
  let bodySize, leadSize, spacing;
  if (bullets.length <= 4) {
    bodySize = 22; leadSize = 24; spacing = 20;
  } else if (bullets.length <= 5) {
    bodySize = 20; leadSize = 22; spacing = 16;
  } else if (bullets.length <= 7) {
    bodySize = 18; leadSize = 20; spacing = 12;
  } else {
    bodySize = 16; leadSize = 18; spacing = 10;
  }

  const textItems = [];
  bullets.forEach((b) => {
    // Support {text, subs} objects for sub-bullets
    if (typeof b === 'object' && b.subs) {
      _pushBulletItem(textItems, b.text, leadSize, bodySize, spacing, C);
      b.subs.forEach(sub => {
        textItems.push({
          text: sub,
          options: {
            fontSize: bodySize - 2,
            color: C.text_body,
            bullet: true,
            indentLevel: 1,
            breakLine: true,
            paraSpaceAfter: spacing / 2,
          }
        });
      });
    } else {
      const text = typeof b === 'string' ? b : b.text;
      _pushBulletItem(textItems, text, leadSize, bodySize, spacing, C);
    }
  });

  slide.addText(textItems, {
    x: M + 0.4, y: CONTENT_Y, w: CONTENT_W - 0.8, h: CONTENT_H,
    valign: "top",
    fontFace: theme.fonts.body,
  });

  if (notes) {
    slide.addNotes(notes);
  }

  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a full-image slide. Image fills the content area with aspect ratio preserved.
 * @param {Object} deck
 * @param {string} title - Slide title
 * @param {string} imagePath - File path or data URI (e.g. "image/png;base64,...")
 * @param {number} slideNum
 * @param {string} [notes] - Optional speaker notes
 */
export function addImageSlide(deck, title, imagePath, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('image') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  const isDataUri = imagePath && imagePath.startsWith("image/");

  if (isDataUri) {
    slide.addImage({
      data: imagePath,
      x: M, y: CONTENT_Y, w: CONTENT_W, h: CONTENT_H,
      sizing: { type: "contain", w: CONTENT_W, h: CONTENT_H },
    });
  } else if (imagePath && existsSync(imagePath)) {
    slide.addImage({
      path: imagePath,
      x: M, y: CONTENT_Y, w: CONTENT_W, h: CONTENT_H,
      sizing: { type: "contain", w: CONTENT_W, h: CONTENT_H },
    });
  } else {
    // Missing file placeholder
    slide.addShape(pptx.ShapeType.rect, {
      x: M, y: CONTENT_Y, w: CONTENT_W, h: CONTENT_H,
      fill: { color: C.surface },
    });
    slide.addText(`[Image: ${imagePath || "unknown"}]`, {
      x: M, y: CONTENT_Y, w: CONTENT_W, h: CONTENT_H,
      fontSize: 14, fontFace: theme.fonts.body,
      color: C.text_secondary, align: "center", valign: "middle",
    });
  }

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add an image + bullets slide. Image on left (~48%), bullets on right (~52%).
 * @param {Object} deck
 * @param {string} title - Slide title
 * @param {string} imagePath - File path or data URI (e.g. "image/png;base64,...")
 * @param {Array<string|{text,subs}>} bullets - Bullet items (same format as addBulletSlide)
 * @param {number} slideNum
 * @param {string} [notes] - Optional speaker notes
 */
export function addImageBulletsSlide(deck, title, imagePath, bullets, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('imageBullets') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  // Split layout: image left ~48%, gutter, bullets right ~52%
  const gutter = 0.36;
  const imgW = (CONTENT_W - gutter) * 0.48;
  const bulletW = CONTENT_W - imgW - gutter;
  const imgX = M;
  const bulletX = M + imgW + gutter;

  const isDataUri = imagePath && imagePath.startsWith("image/");

  if (isDataUri) {
    slide.addImage({
      data: imagePath,
      x: imgX, y: CONTENT_Y, w: imgW, h: CONTENT_H,
      sizing: { type: "contain", w: imgW, h: CONTENT_H },
    });
  } else if (imagePath && existsSync(imagePath)) {
    slide.addImage({
      path: imagePath,
      x: imgX, y: CONTENT_Y, w: imgW, h: CONTENT_H,
      sizing: { type: "contain", w: imgW, h: CONTENT_H },
    });
  } else {
    // Missing file placeholder
    slide.addShape(pptx.ShapeType.rect, {
      x: imgX, y: CONTENT_Y, w: imgW, h: CONTENT_H,
      fill: { color: C.surface },
    });
    slide.addText(`[Image: ${imagePath || "unknown"}]`, {
      x: imgX, y: CONTENT_Y, w: imgW, h: CONTENT_H,
      fontSize: 12, fontFace: theme.fonts.body,
      color: C.text_secondary, align: "center", valign: "middle",
    });
  }

  // Adaptive font size + spacing (same thresholds as addBulletSlide)
  let bodySize, leadSize, spacing;
  if (bullets.length <= 4) {
    bodySize = 20; leadSize = 22; spacing = 16;
  } else if (bullets.length <= 6) {
    bodySize = 18; leadSize = 20; spacing = 12;
  } else {
    bodySize = 16; leadSize = 18; spacing = 10;
  }

  const textItems = [];
  bullets.forEach((b) => {
    if (typeof b === "object" && b.subs) {
      _pushBulletItem(textItems, b.text, leadSize, bodySize, spacing, C);
      b.subs.forEach(sub => {
        textItems.push({
          text: sub,
          options: {
            fontSize: bodySize - 2,
            color: C.text_body,
            bullet: true,
            indentLevel: 1,
            breakLine: true,
            paraSpaceAfter: spacing / 2,
          },
        });
      });
    } else {
      const text = typeof b === "string" ? b : b.text;
      _pushBulletItem(textItems, text, leadSize, bodySize, spacing, C);
    }
  });

  slide.addText(textItems, {
    x: bulletX, y: CONTENT_Y, w: bulletW, h: CONTENT_H,
    valign: "top",
    fontFace: theme.fonts.body,
  });

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add an icon rows slide (items with icon circles or accent bars).
 * @param {Object} deck
 * @param {string} title
 * @param {Array<{label, desc}>} items
 * @param {Array<string>|null} iconImages - base64 icon data URIs (or null for accent bars)
 * @param {number} slideNum
 */
export function addIconRowsSlide(deck, title, items, iconImages, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('iconRows') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  const rowH = items.length > 3 ? 1.1 : 1.4;

  items.forEach((item, i) => {
    const y = CONTENT_Y + i * rowH;

    if (iconImages && iconImages[i]) {
      slide.addShape(pptx.ShapeType.ellipse, {
        x: M + 0.56, y: y, w: 0.7, h: 0.7,
        fill: { color: C.accent },
      });
      slide.addImage({
        data: iconImages[i],
        x: M + 0.68, y: y + 0.12, w: 0.46, h: 0.46,
      });
    } else {
      slide.addShape(pptx.ShapeType.rect, {
        x: M + 0.56, y: y + 0.05, w: 0.06, h: 0.6,
        fill: { color: C.accent },
      });
    }

    slide.addText(item.label, {
      x: M + 1.56, y: y, w: CONTENT_W - 1.56, h: 0.4,
      fontSize: 20, fontFace: theme.fonts.heading,
      color: C.text_primary, bold: true,
    });

    slide.addText(item.desc, {
      x: M + 1.56, y: y + 0.4, w: CONTENT_W - 1.56, h: rowH - 0.5,
      fontSize: 14, fontFace: theme.fonts.body,
      color: C.text_body,
    });
  });

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


// --- Process Flow internals ---

function _addStepBox(slide, pptx, theme, step, index, x, y, w, h) {
  const C = theme.colors;

  slide.addShape(pptx.ShapeType.rect, {
    x, y, w, h,
    fill: { color: C.surface },
    shadow: cardShadow(theme),
  });

  slide.addText(`${index + 1}`, {
    x, y: y + 0.1, w, h: 0.5,
    fontSize: 24, fontFace: theme.fonts.heading,
    color: C.accent, bold: true, align: "center",
  });

  const nlIndex = step.indexOf("\n");
  if (nlIndex > -1) {
    const label = step.substring(0, nlIndex);
    const desc = step.substring(nlIndex + 1);

    slide.addText(label, {
      x: x + 0.1, y: y + 0.65, w: w - 0.2, h: 0.45,
      fontSize: 16, fontFace: theme.fonts.heading,
      color: C.text_primary, bold: true,
      align: "center", valign: "top",
    });

    slide.addText(desc, {
      x: x + 0.1, y: y + 1.1, w: w - 0.2, h: h - 1.3,
      fontSize: 13, fontFace: theme.fonts.body,
      color: C.text_body, align: "center", valign: "top",
    });
  } else {
    slide.addText(step, {
      x: x + 0.1, y: y + 0.7, w: w - 0.2, h: h - 0.9,
      fontSize: 14, fontFace: theme.fonts.body,
      color: C.text_body, align: "center", valign: "top",
    });
  }
}


/**
 * Add a process flow slide with step boxes and arrows.
 * Supports single-row (≤4 steps) and two-row (5+ steps) layouts.
 * Steps can include a label/description split with \n.
 */
export function addProcessFlow(deck, title, steps, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('processFlow') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  const n = steps.length;

  if (n <= 4) {
    const gap = n <= 3 ? 0.6 : 0.4;
    const totalGap = (n - 1) * gap;
    const stepW = Math.min(2.8, (CONTENT_W - totalGap) / n);
    const totalW = n * stepW + totalGap;
    const startX = (SW - totalW) / 2;
    const boxH = 2.8;
    const boxY = CONTENT_Y + (CONTENT_H - boxH) / 2;

    steps.forEach((step, i) => {
      const x = startX + i * (stepW + gap);
      _addStepBox(slide, pptx, theme, step, i, x, boxY, stepW, boxH);

      if (i < n - 1) {
        slide.addText("\u2192", {
          x: x + stepW, y: boxY + boxH / 2 - 0.5, w: gap, h: 1.0,
          fontSize: 28, color: C.accent,
          align: "center", valign: "middle",
        });
      }
    });
  } else {
    const topCount = Math.ceil(n / 2);
    const botCount = n - topCount;
    const gap = 0.35;
    const stepW = Math.min(2.4, (CONTENT_W - (topCount - 1) * gap) / topCount);
    const boxH = 2.2;
    const rowGap = 0.5;
    const totalH = 2 * boxH + rowGap;
    const startY = CONTENT_Y + (CONTENT_H - totalH) / 2;

    // Top row
    const topW = topCount * stepW + (topCount - 1) * gap;
    const topStartX = (SW - topW) / 2;
    for (let i = 0; i < topCount; i++) {
      const x = topStartX + i * (stepW + gap);
      _addStepBox(slide, pptx, theme, steps[i], i, x, startY, stepW, boxH);
      if (i < topCount - 1) {
        slide.addText("\u2192", {
          x: x + stepW, y: startY + boxH / 2 - 0.4, w: gap, h: 0.8,
          fontSize: 24, color: C.accent, align: "center", valign: "middle",
        });
      }
    }

    // Bottom row (centered)
    const botW = botCount * stepW + (botCount - 1) * gap;
    const botStartX = (SW - botW) / 2;
    const botY = startY + boxH + rowGap;
    for (let i = 0; i < botCount; i++) {
      const x = botStartX + i * (stepW + gap);
      _addStepBox(slide, pptx, theme, steps[topCount + i], topCount + i, x, botY, stepW, boxH);
      if (i < botCount - 1) {
        slide.addText("\u2192", {
          x: x + stepW, y: botY + boxH / 2 - 0.4, w: gap, h: 0.8,
          fontSize: 24, color: C.accent, align: "center", valign: "middle",
        });
      }
    }
  }

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a two-column slide with headers and vertical divider.
 */
export function addTwoColumn(deck, title, leftHeader, rightHeader, leftItems, rightItems, slideNum, notes, opts = {}) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('twoColumn') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  const col1W = 5.70;
  const gutter = 0.36;
  const col2X = M + col1W + gutter;
  const col2W = CONTENT_W - col1W - gutter;
  const headerY = CONTENT_Y;
  const bodyY = CONTENT_Y + 0.5;
  const bodyH = CONTENT_H - 0.5;

  const leftHeaderColor = opts.leftHeaderColor || C.accent;
  const rightHeaderColor = opts.rightHeaderColor || C.accent;

  if (leftHeader) {
    slide.addText(leftHeader, {
      x: M, y: headerY, w: col1W, h: 0.45,
      fontSize: 20, fontFace: theme.fonts.heading,
      color: leftHeaderColor, bold: true,
    });
  }
  if (rightHeader) {
    slide.addText(rightHeader, {
      x: col2X, y: headerY, w: col2W, h: 0.45,
      fontSize: 20, fontFace: theme.fonts.heading,
      color: rightHeaderColor, bold: true,
    });
  }

  // Vertical divider
  slide.addShape(pptx.ShapeType.rect, {
    x: M + col1W + gutter / 2 - 0.01, y: CONTENT_Y,
    w: 0.02, h: CONTENT_H,
    fill: { color: C.surface },
  });

  const maxItems = Math.max(leftItems.length, rightItems.length);
  // Font size by density
  const fontSize = maxItems <= 3 ? 17 : maxItems <= 5 ? 16 : maxItems <= 7 ? 15 : 14;
  // Item slot height: distribute items evenly across bodyH so content fills the slide.
  // Each slot gets bodyH / maxItems inches; text renders at top of each slot.
  const slotH = bodyH / maxItems;

  const renderColItems = (items, x, w) => {
    items.forEach((item, i) => {
      const y = bodyY + i * slotH;
      const textItems = [];
      _pushBulletItem(textItems, item, fontSize, fontSize, 4, C);
      slide.addText(textItems, {
        x, y, w, h: slotH,
        valign: "middle",
        fontFace: theme.fonts.body,
      });
    });
  };

  renderColItems(leftItems, M, col1W);
  renderColItems(rightItems, col2X, col2W);

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a card grid slide (2x2 or 2x3 layout).
 */
export function addCardGrid(deck, title, cards, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('cardGrid') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  const n = cards.length;
  const cols = n === 3 ? 3 : n <= 4 ? 2 : 3;
  const rows = Math.ceil(n / cols);
  const gap = 0.4;
  const cardW = (CONTENT_W - (cols - 1) * gap) / cols;
  const cardH = (CONTENT_H - (rows - 1) * gap) / rows;

  cards.forEach((card, i) => {
    const col = i % cols;
    const row = Math.floor(i / cols);
    const x = M + col * (cardW + gap);
    const y = CONTENT_Y + row * (cardH + gap);
    const accentColor = card.accent || [C.accent, C.accent_alt, C.warning, C.accent][i % 4];

    slide.addShape(pptx.ShapeType.rect, {
      x, y, w: cardW, h: cardH,
      fill: { color: C.surface },
      shadow: cardShadow(theme),
    });

    slide.addShape(pptx.ShapeType.rect, {
      x, y, w: 0.06, h: cardH,
      fill: { color: accentColor },
    });

    if (card.iconImg) {
      slide.addShape(pptx.ShapeType.ellipse, {
        x: x + 0.25, y: y + 0.25, w: 0.55, h: 0.55,
        fill: { color: C.background },
      });
      slide.addImage({
        data: card.iconImg,
        x: x + 0.33, y: y + 0.33, w: 0.39, h: 0.39,
      });
    }

    const titleX = card.iconImg ? x + 0.95 : x + 0.25;
    const titleW = card.iconImg ? cardW - 1.1 : cardW - 0.45;
    slide.addText(card.title, {
      x: titleX, y: y + 0.2, w: titleW, h: 0.55,
      fontSize: 18, fontFace: theme.fonts.heading,
      color: C.text_primary, bold: true,
      valign: "middle",
    });

    slide.addText(card.body, {
      x: x + 0.25, y: y + 0.85, w: cardW - 0.45, h: cardH - 1.1,
      fontSize: 14, fontFace: theme.fonts.body,
      color: C.text_body, valign: "top",
    });
  });

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a stat/callout slide with large numbers.
 */
export function addStatCallout(deck, title, stats, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('statCallout') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  const n = stats.length;
  const gap = 0.5;
  const statW = (CONTENT_W - (n - 1) * gap) / n;

  stats.forEach((stat, i) => {
    const x = M + i * (statW + gap);
    const y = CONTENT_Y + CONTENT_H * 0.15;

    slide.addText(stat.value, {
      x, y, w: statW, h: 1.2,
      fontSize: T.stat_size, fontFace: theme.fonts.heading,
      color: C.stat_color || C.accent, bold: T.stat_bold,
      align: "center",
    });

    slide.addText(stat.label, {
      x, y: y + 1.3, w: statW, h: 0.6,
      fontSize: T.stat_label_size, fontFace: theme.fonts.body,
      color: C.text_body,
      align: "center",
    });

    if (stat.desc) {
      slide.addText(stat.desc, {
        x, y: y + 2.0, w: statW, h: 0.8,
        fontSize: T.stat_desc_size, fontFace: theme.fonts.body,
        color: C.text_secondary,
        align: "center",
      });
    }
  });

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a code block slide.
 */
export function addCodeSlide(deck, title, code, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const { M, CONTENT_W, CONTENT_Y, CONTENT_H } = layout;
  const C = theme.colors;
  const T = theme.typography;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('code') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  slide.addText(title, {
    x: M, y: 0.3, w: CONTENT_W, h: 0.7,
    fontSize: T.heading_size, fontFace: theme.fonts.heading,
    color: C.heading_color || C.text_primary, bold: true,
  });

  slide.addShape(pptx.ShapeType.rect, {
    x: M, y: CONTENT_Y, w: CONTENT_W, h: CONTENT_H,
    fill: { color: C.code_bg },
  });

  slide.addShape(pptx.ShapeType.rect, {
    x: M, y: CONTENT_Y, w: CONTENT_W, h: 0.05,
    fill: { color: C.accent },
  });

  slide.addText(code, {
    x: M + 0.3, y: CONTENT_Y + 0.25, w: CONTENT_W - 0.6, h: CONTENT_H - 0.4,
    fontSize: T.code_size, fontFace: theme.fonts.mono,
    color: C.code_text,
    valign: "top",
    paraSpaceAfter: 6,
  });

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a section divider slide (numbered panel on left, title right).
 */
export function addSectionDivider(deck, sectionNumber, title, slideNum) {
  const { pptx, theme, layout } = deck;
  const { M } = layout;
  const C = theme.colors;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('sectionDivider') }
    : {};
  const slide = pptx.addSlide(slideOpts);

  const panelW = SW * 0.18;

  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
    slide.addShape(pptx.ShapeType.rect, {
      x: 0, y: 0, w: panelW, h: SH,
      fill: { color: C.background_alt },
    });
  }

  const numStr = String(sectionNumber).padStart(2, "0");
  slide.addText(numStr, {
    x: 0, y: SH * 0.3, w: panelW, h: 1.5,
    fontSize: 96, fontFace: theme.fonts.heading,
    color: C.text_secondary, bold: true,
    align: "center", valign: "middle",
    transparency: 70,
  });

  if (!deck.useSlideMaster) {
    slide.addShape(pptx.ShapeType.rect, {
      x: panelW - 0.04, y: 0, w: 0.04, h: SH,
      fill: { color: C.accent },
    });
  }

  const rightX = panelW + 0.6;
  const rightW = SW - rightX - M;

  slide.addText("SECTION", {
    x: rightX, y: SH * 0.35, w: rightW, h: 0.4,
    fontSize: 12, fontFace: theme.fonts.body,
    color: C.text_secondary,
    charSpacing: 6,
  });

  slide.addText(title, {
    x: rightX, y: SH * 0.42, w: rightW, h: 1.2,
    fontSize: 42, fontFace: theme.fonts.heading,
    color: C.text_primary, bold: true,
  });

  slide.addShape(pptx.ShapeType.rect, {
    x: rightX, y: SH * 0.42 + 1.25, w: 2.0, h: 0.06,
    fill: { color: C.accent },
  });

  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme);
  }
  return slide;
}


/**
 * Add a closing slide (AMD style: centered wordmark, no footer).
 */
export function addClosingSlide(deck, slideNum, notes) {
  const { pptx, theme, layout } = deck;
  const C = theme.colors;
  const slideOpts = deck.useSlideMaster
    ? { masterName: masterNameFor('closing') }
    : {};
  const slide = pptx.addSlide(slideOpts);
  if (!deck.useSlideMaster) {
    slide.background = { color: C.background };
  }

  if (theme.logo.path && existsSync(theme.logo.path)) {
    slide.addImage({
      path: theme.logo.path,
      x: (SW - 4.0) / 2, y: (SH - 1.14) / 2, w: 4.0, h: 1.14,
    });
  } else {
    slide.addText("Thank You", {
      x: 1, y: (SH - 1.2) / 2, w: SW - 2, h: 1.2,
      fontSize: 48, fontFace: theme.fonts.heading,
      color: theme.colors.text_primary, bold: true,
      align: "center", valign: "middle",
    });
  }

  if (notes) slide.addNotes(notes);
  if (!deck.useSlideMaster) {
    addFooter(slide, slideNum, theme, { suppressLogo: true, suppressNumber: true });
  }
  return slide;
}


// ═══════════════════════════════════════════════════════════════
// Deck Lifecycle
// ═══════════════════════════════════════════════════════════════

/**
 * Create a new deck with theme and layout computed.
 * @param {string} themePath - Path to themes/*.yaml
 * @param {{ useSlideMaster?: boolean }} [opts] - Options
 * @returns {{ pptx, theme, layout, useSlideMaster, save(path) }}
 */
export function createDeck(themePath, opts = {}) {
  const pptxgen = require("pptxgenjs");
  const theme = loadTheme(themePath);
  if (opts.overrides) {
    deepMerge(theme, opts.overrides);
  }
  const layout = computeLayout(theme);
  const useSlideMaster = opts.useSlideMaster ?? false;

  const pptx = new pptxgen();
  pptx.layout = theme.slide.layout;

  const deck = {
    pptx,
    theme,
    layout,
    useSlideMaster,
    async save(outputPath) {
      await pptx.writeFile({ fileName: outputPath });
      if (existsSync(outputPath)) {
        const stats = statSync(outputPath);
        console.log(`Deck saved: ${outputPath} (${(stats.size / 1024).toFixed(0)} KB)`);
      }
    },
  };

  if (useSlideMaster) {
    defineMasters(deck);
  }

  return deck;
}

export { masterNameFor } from './pptxgenjs-masters.mjs';
