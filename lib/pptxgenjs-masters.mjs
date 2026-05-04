/**
 * pptxgenjs-masters.mjs — slide master definitions for pptxgenjs engine.
 *
 * Called from createDeck() when opts.useSlideMaster is true.
 */

import { SW, SH } from './pptxgenjs-helpers.mjs';
import { existsSync } from 'fs';

const LAYOUT_TYPES = {
  title: 'TITLE_MASTER',
  closing: 'TITLE_MASTER',
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
    background: { color: titleBg },
    objects: titleObjects,
  });

  // --- CONTENT_MASTER ---
  const contentBg = masterOverrides.content?.background || C.background;
  const contentObjects = [];
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
    background: { color: contentBg },
    objects: contentObjects,
    slideNumber: {
      x: 0.2, y: SH - 0.45,
      fontSize: 10, fontFace: theme.fonts.body,
      color: C.text_primary,
    },
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
