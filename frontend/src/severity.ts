import type { Severity } from "./types";

/**
 * Severity ramp, validated for colour-vision deficiency against the console's
 * paper surface (#f8f8f5) with scripts/validate_palette.js: every adjacent pair
 * clears the normal-vision floor (worst 18.7) and CVD separation (worst 18.0
 * protan), all four sit inside the lightness band, hold the chroma floor, and
 * reach 3:1 contrast against the surface.
 *
 * The console's earlier coral/amber pair measured ΔE 10.6 for normal vision,
 * below the floor of 15 — on a night shift, severity is the first thing a keeper
 * reads, so the two most urgent states must not look alike.
 *
 * Severity is never carried by colour alone: every use pairs a swatch with the
 * severity word.
 */
export const SEVERITY_COLOR: Record<Severity, string> = {
  CRITICAL: "#a02717",
  HIGH: "#bf8410",
  MODERATE: "#2b6cb0",
  LOW: "#3f8f5f",
  NONE: "#68716d"
};

export const SEVERITY_ORDER: Severity[] = [
  "CRITICAL",
  "HIGH",
  "MODERATE",
  "LOW"
];

export const SEVERITY_RANK: Record<Severity, number> = {
  CRITICAL: 4,
  HIGH: 3,
  MODERATE: 2,
  LOW: 1,
  NONE: 0
};

/** Single hue used wherever one measure is compared across entities. */
export const MEASURE_HUE = "#285747";
export const MOTION_HUE = "#2b6cb0";
