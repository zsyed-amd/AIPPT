/**
 * pptxgenjs-masters.mjs — slide master definitions for pptxgenjs engine.
 *
 * Called from createDeck() when opts.useSlideMaster is true.
 */

import { SW, SH } from './pptxgenjs-helpers.mjs';
import { existsSync } from 'fs';

const LAYOUT_TYPES = {
  title: 'TITLE_MASTER',
  closing: 'CLOSING_MASTER',
  bullet: 'CONTENT_MASTER',
  image: 'CONTENT_MASTER',
  imageBullets: 'CONTENT_MASTER',
  processFlow: 'CONTENT_MASTER',
  twoColumn: 'CONTENT_MASTER',
  cardGrid: 'CONTENT_MASTER',
  statCallout: 'CONTENT_MASTER',
  code: 'CONTENT_MASTER',
  iconRows: 'CONTENT_MASTER',
  sectionDivider: 'SECTION_DIVIDER_MASTER',
};

export function masterNameFor(layoutType) {
  return LAYOUT_TYPES[layoutType] || 'CONTENT_MASTER';
}

export function defineMasters(deck) {
  const { pptx, theme } = deck;
  const C = theme.colors;
  const masterOverrides = theme.master || {};
  const bgImage = masterOverrides.background_image
    && existsSync(masterOverrides.background_image)
    ? masterOverrides.background_image : null;

  // --- TITLE_MASTER ---
  const titleBg = masterOverrides.title?.background || C.background_alt;
  const titleObjects = [];
  if (theme.logo.path && existsSync(theme.logo.path)) {
    titleObjects.push({
      image: {
        path: theme.logo.path,
        x: theme.logo.x, y: theme.logo.y,
        w: theme.logo.width, h: theme.logo.height,
      },
    });
  }
  pptx.defineSlideMaster({
    title: 'TITLE_MASTER',
    background: bgImage ? { path: bgImage } : { color: titleBg },
    objects: titleObjects,
  });

  // --- CONTENT_MASTER ---
  const contentBg = masterOverrides.content?.background || C.background;
  const contentObjects = [];

  // Eyebrow rule is drawn per-slide by addEyebrowText() when needed,
  // not on the master — it interferes with titles on standard content slides.

  // Optional glow-line divider: thin accent line below the heading area
  if (masterOverrides.content?.glow_line) {
    const margin = theme.slide?.margin || 0.5;
    const lineW = SW - 2 * margin;
    contentObjects.push({
      rect: {
        x: margin, y: 1.08, w: lineW, h: 0.025,
        fill: { color: C.accent },
      },
    });
  }

  if (theme.logo.path && existsSync(theme.logo.path)) {
    contentObjects.push({
      image: {
        path: theme.logo.path,
        x: theme.logo.x, y: theme.logo.y,
        w: theme.logo.width, h: theme.logo.height,
      },
    });
  }
  pptx.defineSlideMaster({
    title: 'CONTENT_MASTER',
    background: bgImage ? { path: bgImage } : { color: contentBg },
    objects: contentObjects,
    slideNumber: {
      x: 0.2, y: SH - 0.45,
      fontSize: theme.typography.footer_size, fontFace: theme.fonts.body,
      color: C.text_primary,
    },
  });

  // --- CLOSING_MASTER (like TITLE_MASTER but no footer logo) ---
  pptx.defineSlideMaster({
    title: 'CLOSING_MASTER',
    background: bgImage ? { path: bgImage } : { color: titleBg },
    objects: [],
  });

  // --- SECTION_DIVIDER_MASTER ---
  const panelPct = masterOverrides.section_divider?.panel_width_pct || 18;
  const panelW = SW * (panelPct / 100);
  pptx.defineSlideMaster({
    title: 'SECTION_DIVIDER_MASTER',
    background: { color: C.background },
    objects: [
      {
        rect: {
          x: 0, y: 0, w: panelW, h: SH,
          fill: { color: C.background_alt },
        },
      },
      {
        rect: {
          x: panelW - 0.04, y: 0, w: 0.04, h: SH,
          fill: { color: C.accent },
        },
      },
    ],
  });
}
