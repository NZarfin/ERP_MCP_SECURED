import type { Config } from "tailwindcss";

// "Market ledger" design system: a dense, dark, trading-floor-for-produce aesthetic.
// Fresh-produce green as the one saturated accent against near-black charcoal; amber
// and rust reserved strictly for status. See apps/web/README.md for the rationale.
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        ink: {
          bg: "#14161A",
          surface: "#1B1E23",
          raised: "#23272E",
          border: "#2E333B",
          borderStrong: "#3A404A",
        },
        paper: {
          primary: "#ECEDEE",
          secondary: "#9CA3AB",
          muted: "#6B7280",
        },
        crop: {
          DEFAULT: "#5FAE62",
          hover: "#74C378",
          dim: "#2E4A31",
          text: "#8FD192",
        },
        amber: {
          DEFAULT: "#D9A441",
          dim: "#4A3B1E",
          text: "#E8C077",
        },
        rust: {
          DEFAULT: "#C1595A",
          dim: "#492425",
          text: "#E08A8B",
        },
        slate: {
          DEFAULT: "#8B93A1",
          dim: "#2A2E36",
          text: "#B7BEC9",
        },
      },
      fontFamily: {
        display: ["var(--font-fraunces)", "Georgia", "serif"],
        sans: ["var(--font-plex-sans)", "system-ui", "sans-serif"],
        mono: ["var(--font-plex-mono)", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
