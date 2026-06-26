// Light mode — enterprise NIC colour tokens
export const T = {
  base:    "#f0f3f8",
  surface: "#ffffff",
  raised:  "#f6f8fc",
  hover:   "#eaeff8",
  panel:   "#ffffff",
  bd:      "#dce1ee",
  bdl:     "#eaecf5",
  pri:     "#0f1729",
  sec:     "#475680",
  mut:     "#8e9ab8",
  ok:      "#0a7c52",
  warn:    "#c47a0a",
  crit:    "#d42b2b",
  info:    "#1a56db",
  purp:    "#6d28d9",
  acct:    "#1a56db",
} as const;

export const TT = {
  contentStyle: {
    background:   "#ffffff",
    border:       "1px solid #dce1ee",
    borderRadius: 4,
    fontSize:     11,
    fontFamily:   "JetBrains Mono, monospace",
    boxShadow:    "0 4px 12px rgba(15,23,41,0.10)",
  },
  labelStyle:  { color: "#475680" },
  itemStyle:   { color: "#0f1729" },
  cursor:      { stroke: "#dce1ee" },
} as const;

export const ATTACK_COLOR: Record<string, string> = {
  Normal: "#0a7c52",
  DoS:    "#d42b2b",
  Probe:  "#c47a0a",
  R2L:    "#1a56db",
  U2R:    "#6d28d9",
};

// Lighter fill variants for chart areas / row highlights
export const ATTACK_BG: Record<string, string> = {
  Normal: "#dcfce7",
  DoS:    "#fee2e2",
  Probe:  "#fef3c7",
  R2L:    "#dbeafe",
  U2R:    "#ede9fe",
};
