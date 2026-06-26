/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Light mode — enterprise NIC palette
        base:    "#f0f3f8",   // main canvas background
        surface: "#ffffff",   // card / panel background
        raised:  "#f6f8fc",   // elevated elements, table headers
        hover:   "#eaeff8",   // hover states
        panel:   "#ffffff",   // sidebar
        bd:      "#dce1ee",   // borders
        bdl:     "#eaecf5",   // light borders / separators
        pri:     "#0f1729",   // primary text
        sec:     "#475680",   // secondary text
        mut:     "#8e9ab8",   // muted / placeholder
        ok:      "#0a7c52",   // green
        warn:    "#c47a0a",   // amber
        crit:    "#d42b2b",   // red
        info:    "#1a56db",   // blue
        purp:    "#6d28d9",   // purple
        acct:    "#1a56db",   // accent (corporate blue)
      },
      fontFamily: {
        mono: ["JetBrains Mono", "ui-monospace", "Consolas", "monospace"],
        sans: ["Inter", "system-ui", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
      },
    },
  },
  plugins: [],
};
