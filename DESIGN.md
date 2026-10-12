---
name: CodeLens demo page
description: A surveyor's plat of a live codebase analysis — every claim staked to coordinates.
colors:
  paper: "#f5f1e6"
  paper-deep: "#ece5d3"
  ink: "#1c2530"
  ink-soft: "#425062"
  flag-orange: "#b34a1b"
  flag-orange-deep: "#8f3a12"
  verified: "#1b6b3c"
  verified-ground: "#e3ecdd"
  void: "#b3362b"
  void-ground: "#f3e2da"
  inferred: "#8a5f14"
  inferred-ground: "#f0e6c8"
  focus: "#0f5fd0"
typography:
  display:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "2.6rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.02em"
  body:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Helvetica Neue, Arial, sans-serif"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.4
    letterSpacing: "0.1em"
  mono:
    fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
    fontSize: "0.9rem"
rounded:
  card: "12px"
  control: "999px"
  field: "8px"
  key: "4px"
spacing:
  section: "20px"
  sheet: "24px"
  group: "10px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    rounded: "{rounded.control}"
    padding: "0.55rem 1.15rem"
  button-primary-hover:
    backgroundColor: "#000000"
  button-ghost:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "0.55rem 1.15rem"
  input-field:
    backgroundColor: "#ffffff"
    textColor: "{colors.ink}"
    rounded: "{rounded.field}"
    padding: "0.55rem 0.7rem"
  ref-verified:
    backgroundColor: "{colors.verified-ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
  ref-rejected:
    backgroundColor: "{colors.void-ground}"
    textColor: "{colors.ink}"
    rounded: "{rounded.card}"
---

# Design System: CodeLens demo page

## Overview

**Creative North Star: "The Surveyor's Plat"**

A measured drawing of a live analysis. The page behaves like a survey sheet: a drawing frame with corner ticks and a sheet mark, one ruled band of instruments, and a result sheet where every model claim is staked to file:line coordinates. Verified references are inked monuments on green ground; rejected ones are void stamps on red ground with their reasons. Color never decorates — it testifies. The single authored motion is the chainage tally that ticks an honest elapsed timer while the local model works. Density is high but ruled; nothing floats without a line anchoring it.

**Key Characteristics:**
- Ruled and restrained: flat 1px ink borders, one soft shadow reserved for the result sheet.
- Coordinates are the interface: mono file:line callouts with margin keys, evidence quotes beneath.
- Failure is first-class: voids and INFERRED verdicts render as designed states, never as errors to hide.

## Colors

Drafting-paper ground with iron ink; one flag orange for pins, chainage, and markers; green/red/amber doing only verification-state jobs.

### Primary
- **Flag Orange** (#b34a1b): pins, chainage ticks, sheet-mark corners, model tag. Never body text on paper at small sizes; deep variant (#8f3a12, 6.69:1) carries text duty.

### Secondary
- **Iron Ink** (#1c2530): text, rules, borders, primary button fill. Paper text on it runs 13.72:1.

### Tertiary
- **Verified Green** (#1b6b3c on #e3ecdd, 5.38:1): monuments only.
- **Void Red** (#b3362b on #f3e2da, 4.80:1): void stamps and reasons only.
- **Inferred Amber** (#8a5f14 on #f0e6c8): reserved for undecided states.

### Neutral
- **Drafting Paper** (#f5f1e6): ground, with a 28px hairline survey grid at 7% ink.
- **Deep Paper** (#ece5d3): hover washes and secondary grounds.
- **Ink Soft** (#425062, 7.28:1): secondary prose, labels, table headers — tinted from the ink hue, never gray.
- **Focus Blue** (#0f5fd0, 5.22:1): keyboard focus rings only.

### Named Rules
**The Testimony Rule.** A color on screen must be doing a state, coordinate, or instrument job. If it is only pretty, it leaves.
**The Ground Rule.** State colors appear only on their tinted grounds, never as bare text on paper.
**The Night-Shift Rule.** The dark theme is the same plat after hours, not a second identity: identical rules, ticks, and badges on a dark ink ground (`--paper` #161e29), with every text pair recomputed to 4.5:1 or better. Toggle persists in `localStorage`, honors `prefers-color-scheme` on first visit, and flips via `data-theme` on the root — no new components, no new palette roles.

## Typography

**Display Font:** system grotesk stack (-apple-system through Arial). **Body Font:** same stack. **Label/Mono Font:** ui-monospace stack for coordinates, code, timers, and path input.

**Character:** workhorse pairing — the voice is the measurement, not the letterforms. No display face with a point of view; the world speaks through rules, ticks, and stamps.

### Hierarchy
- **Display** (800, 2.6rem/1.05, -0.02em): page title only.
- **Headline** (700 inherited, 1rem): sheet and evidence-group headings; evidence groups are 0.8rem uppercase labels at 0.12em instead.
- **Body** (400, 16px/1.55): answer prose at 65–72ch measure.
- **Label** (400, 12px, 0.1–0.14em, uppercase): field labels, sheet mark, table headers. Wide tracking lives only here.
- **Mono** (0.82–0.95rem, tabular numerals): coordinates, quotes, paths, timers.

### Named Rules
**The Tabular Rule.** Every number a user compares — line ranges, counts, timers — sets in tabular numerals.

## Layout

Single column, 1060px frame: title block → instrument band (ruled top and bottom, controls wrap) → result sheet → footer. Evidence refs are full-width ruled entries, not a side rail, so the 720px breakpoint only stacks the title row and hides inline reasons. Spacing rhythm: 20px between regions, 24px sheet padding, 10px inside groups; more space above headings than below.

## Elevation & Depth

Flat by construction. Depth is conveyed by grounds (paper → deep paper → white entries) and one soft offset shadow (`8px 8px 0 rgba(28,37,48,0.12)`) reserved for the pinned result sheet.

**The One Shadow Rule.** Only the result sheet casts. Everything else earns separation with a rule or a ground change.

## Shapes

Rectilinear survey language: 12px card radius, pill controls (999px), 8px fields, 4px key chips. Corner ticks pin the title block. Badges are drawn 1.5-stroke SVG (monument pin, void seal, query diamond) in currentColor — never emoji or glyph icons.

## Components

### Buttons
- **Shape:** pill (999px), 1px ink border.
- **Primary:** ink fill, paper text, semibold; hover goes black. Ask is the only primary.
- **Hover / Focus:** ghost buttons wash deep-paper; all controls show a 2px focus-blue ring at 2px offset.
- **Secondary:** paper fill, ink text (Scan, Analyze).

### Monument / Void refs
- **Shape:** 12px card, 1px ink border, white-to-ground fill.
- **Verified:** green ground, pin badge, margin key chip (K1…), mono coordinate, quoted evidence in a dashed-rule drawer (`<details>`).
- **Rejected:** red ground, void badge, reason right-aligned, V-key chip.
- **Behavior:** opening one entry dims its siblings (focus swell); keyboard-native via details/summary.

### Inputs / Fields
- **Style:** white fill, 1px ink stroke, 8px radius; uppercase 12px label above.
- **Focus:** focus-blue ring. **Error / Disabled:** instrument buttons disable with 0.45 opacity and wait cursor during model calls.

### Schedule table
- **Style:** borderless rows, 1px bottom rules, uppercase soft-ink headers, tabular numerals; mono for paths.

### Chainage ticker
- **Style:** dashed orange rule, animated tick strip, mono elapsed timer. Reports real elapsed time only — never staged progress.

### Listen bar
- **Style:** surface card, 1px ink border; uppercase soft-ink heading; pill buttons, selects for section/voice/speed.
- **Behavior:** narrates rendered bullets in order via speechSynthesis (no new content); current bullet and section highlight in inferred-amber wash with accent outline; status line names section and bullet position.

### Navigation
No site navigation; single surface. Section order is the wayfinding.

## Do's and Don'ts

### Do:
- **Do** stake every model claim to a coordinate with its verification state attached.
- **Do** render voids with reasons — a rejected reference is content, not an error.
- **Do** keep all text pairs at 4.5:1 or better (verified pairs computed, not eyeballed) — in both themes.
- **Do** escape all model text before rendering — answers are untrusted data.

### Don't:
- **Don't** add a chat window, kickers, section numbers, gradient text, or colored left borders — the floor bans stand.
- **Don't** use orange as body text or fill for small text — contrast fails; deep variant or graphic duty only.
- **Don't** invent refs, timings, or file contents — empty and INFERRED states are designed outcomes.
- **Don't** add web dependencies, hosted fonts, or CDN assets — the server stays stdlib-only and offline-capable.
