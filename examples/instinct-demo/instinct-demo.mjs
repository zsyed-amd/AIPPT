/**
 * instinct-demo.mjs — AMD Instinct theme showcase deck.
 *
 * Usage (from project root):
 *   NODE_PATH="$(npm root -g)" node examples/instinct-demo/instinct-demo.mjs
 *
 * Output: examples/instinct-demo/instinct-demo.pptx
 */

import {
  createDeck,
  addBulletSlide,
  addSectionDivider,
  addTwoColumn,
  addCardGrid,
  addStatCallout,
  addProcessFlow,
  addCodeSlide,
  addClosingSlide,
  addEyebrowText,
  SW, SH,
} from '../../lib/pptxgenjs-helpers.mjs';
import { masterNameFor } from '../../lib/pptxgenjs-masters.mjs';

const deck = createDeck('themes/instinct.yaml', { useSlideMaster: true });
const { pptx, theme, layout } = deck;
const C = theme.colors;
const M = layout.M;
let sn = 1;

// ═══════════════════════════════════════════════════════
// Slide 1: Title — custom typographic layout, no squished logo
// ═══════════════════════════════════════════════════════
{
  const slide = pptx.addSlide({ masterName: masterNameFor('title') });

  // Atmospheric teal glow — large diffuse ellipse right-of-center
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 7.8, y: 0.8, w: 6.0, h: 6.0,
    fill: { color: '00C2DE', transparency: 94 },
    line: { type: 'none' },
  });

  // Eyebrow: short teal rule + label
  slide.addShape(pptx.ShapeType.rect, {
    x: M, y: 2.55, w: 0.9, h: 0.025,
    fill: { color: C.accent },
    line: { type: 'none' },
  });
  slide.addText('AMD INSTINCT PLATFORM', {
    x: M + 1.05, y: 2.48, w: 6.0, h: 0.18,
    fontSize: 9, fontFace: theme.fonts.body,
    color: C.accent, charSpacing: 7, bold: false,
  });

  // Main title — large, confident
  slide.addText('AMD Instinct\nMI300X', {
    x: M, y: 2.75, w: 8.5, h: 2.2,
    fontSize: 56, fontFace: theme.fonts.heading,
    color: C.text_primary, bold: true,
    lineSpacingMultiple: 1.0,
  });

  // Teal accent bar
  slide.addShape(pptx.ShapeType.rect, {
    x: M, y: 5.1, w: 3.0, h: 0.045,
    fill: { color: C.accent },
    line: { type: 'none' },
  });

  // Subtitle
  slide.addText('Next-Generation Data Center Accelerators\nfor AI and HPC Workloads', {
    x: M, y: 5.25, w: 8.5, h: 0.9,
    fontSize: 18, fontFace: theme.fonts.body,
    color: C.text_secondary, lineSpacingMultiple: 1.3,
  });

  // Sensitivity label bottom-left
  slide.addText('AMD Confidential — Internal Distribution Only', {
    x: M, y: 7.05, w: 6.0, h: 0.22,
    fontSize: 8, fontFace: theme.fonts.body,
    color: C.text_secondary, charSpacing: 2,
  });

  sn++;
}

// ═══════════════════════════════════════════════════════
// Slide 2: Section Divider
// ═══════════════════════════════════════════════════════
addSectionDivider(deck, 1, 'Platform Overview', sn++);

// ═══════════════════════════════════════════════════════
// Slide 3: Why MI300X — bullets
// ═══════════════════════════════════════════════════════
{
  const slide = addBulletSlide(
    deck,
    'Why AMD Instinct MI300X',
    [
      '**192 GB unified HBM3** — largest memory footprint in class, enabling models too large to fit elsewhere',
      '**Open ecosystem** — ROCm, PyTorch, JAX, vLLM: no lock-in, no tax on access',
      '**Proven at hyperscale** — deployed in El Capitan (#1 TOP500), Microsoft Azure ND series',
      '**OCP-compliant OAM** — standard form factor across all MI300 SKUs, integrates with existing rack designs',
    ],
    sn++,
    'Lead with memory capacity — that is the MI300X differentiator for LLM inference.',
  );
  addEyebrowText(slide, 'Platform Overview', theme);
}

// ═══════════════════════════════════════════════════════
// Slide 4: Gen-on-gen comparison
// ═══════════════════════════════════════════════════════
{
  const slide = addTwoColumn(
    deck,
    'MI300X vs. MI250X — Generational Leap',
    'MI300X', 'MI250X',
    [
      '192 GB HBM3 unified memory',
      '5.3 TB/s aggregate bandwidth',
      '1,307 TFLOPS FP16 / 2,614 TOPS INT8',
      'Unified GPU + CPU memory architecture',
      'PCIe Gen 5 + 7th-gen Infinity Fabric',
    ],
    [
      '128 GB HBM2e (split across two GCDs)',
      '3.2 TB/s aggregate bandwidth',
      '383 TFLOPS FP16 / 383 TOPS INT8',
      'Discrete GPU only',
      'PCIe Gen 4 + 3rd-gen Infinity Fabric',
    ],
    sn++,
    'Memory capacity doubles; bandwidth increases 1.65×; compute increases 3.4× FP16.',
  );
  addEyebrowText(slide, 'Platform Overview', theme);
}

// ═══════════════════════════════════════════════════════
// Slide 5: Software stack — card grid
// ═══════════════════════════════════════════════════════
{
  const slide = addCardGrid(
    deck,
    'Open Software Stack',
    [
      { title: 'ROCm', body: 'Open-source GPU compute platform. HIP, rocBLAS, MIOpen, hipBLASLt, rocFFT — full parity with CUDA math libraries.' },
      { title: 'PyTorch', body: 'Native ROCm support merged upstream. torch.compile and SDPA kernels tuned for MI300X memory architecture.' },
      { title: 'vLLM', body: 'High-throughput LLM inference via PagedAttention. Chunked prefill and speculative decoding supported on MI300X.' },
      { title: 'JAX / XLA', body: 'XLA compiler backend for ROCm fully validated. Research and production workloads at scale.' },
    ],
    sn++,
  );
  addEyebrowText(slide, 'Platform Overview', theme);
}

// ═══════════════════════════════════════════════════════
// Slide 6: Section Divider
// ═══════════════════════════════════════════════════════
addSectionDivider(deck, 2, 'Performance', sn++);

// ═══════════════════════════════════════════════════════
// Slide 7: Stat callout — inference performance
// ═══════════════════════════════════════════════════════
{
  const slide = addStatCallout(
    deck,
    'Inference Performance vs. H100 SXM5',
    [
      { value: '1.3×', label: 'Llama 3.1 405B', desc: 'Output tokens/sec' },
      { value: '1.2×', label: 'Mixtral 8×22B', desc: 'Output tokens/sec' },
      { value: '2.4×', label: 'Memory Capacity', desc: '192 GB vs. 80 GB' },
    ],
    sn++,
    'GeoMean across batch sizes 1–512. Source: AMD internal, ROCm 6.3, vLLM 0.6.x. Competitor measured on identical hardware configuration.',
  );
  addEyebrowText(slide, 'Performance', theme);
}

// ═══════════════════════════════════════════════════════
// Slide 8: Deployment workflow
// ═══════════════════════════════════════════════════════
{
  const slide = addProcessFlow(
    deck,
    'Cluster Deployment Workflow',
    [
      'Provision\nOAM baseboard\n+ host server',
      'Install\nROCm 6.x\n+ kernel driver',
      'Configure\nvLLM or TGI\nserving framework',
      'Validate\nBenchmark with\nreference models',
    ],
    sn++,
    'Typical time-to-inference from bare metal: 4–6 hours including driver install and model download.',
  );
  addEyebrowText(slide, 'Deployment', theme);
}

// ═══════════════════════════════════════════════════════
// Slide 9: Code slide
// ═══════════════════════════════════════════════════════
{
  const slide = addCodeSlide(
    deck,
    'Quick Start: vLLM on MI300X',
    `# Pull and launch vLLM — MI300X optimized image
docker run --device /dev/kfd --device /dev/dri \\
  --group-add video --shm-size 16g \\
  -p 8000:8000 \\
  rocm/vllm-openai:latest \\
  --model meta-llama/Llama-3.1-70B-Instruct \\
  --tensor-parallel-size 4 \\
  --max-model-len 131072 \\
  --gpu-memory-utilization 0.92

# Query the endpoint
curl http://localhost:8000/v1/chat/completions \\
  -H "Content-Type: application/json" \\
  -d '{"model":"meta-llama/Llama-3.1-70B-Instruct",
       "messages":[{"role":"user","content":"Explain HBM3"}]}'`,
    sn++,
    'Use tensor-parallel-size=8 for 405B models. The 192 GB unified memory eliminates model sharding for most 70B–130B parameter models.',
  );
  addEyebrowText(slide, 'Deployment', theme);
}

// ═══════════════════════════════════════════════════════
// Slide 10: Closing
// ═══════════════════════════════════════════════════════
addClosingSlide(deck, sn++);

await deck.save('examples/instinct-demo/instinct-demo.pptx');
