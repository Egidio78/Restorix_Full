import type { Config } from "tailwindcss";
import { createRequire } from "module";

const require = createRequire(import.meta.url);

const config: Config = {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Restorix Premium Dark palette (rx- prefix to avoid shadcn collisions)
        "rx-bg": {
          DEFAULT: "#0c1929",
          elevated: "#0a1424",
          surface: "#1e3a5f",
        },
        "rx-accent": {
          DEFAULT: "#34d399",
          bright: "#10b981",
          deep: "#047857",
        },
        "rx-ink": {
          DEFAULT: "#f1f5f9",
          muted: "#94a3b8",
          faint: "#64748b",
        },
        "rx-border": "#1e3a5f",
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'Consolas', 'monospace'],
      },
      boxShadow: {
        'rx-glow': '0 4px 12px rgba(52, 211, 153, 0.25)',
        'rx-card': '0 1px 3px rgba(0, 0, 0, 0.1)',
      },
      backgroundImage: {
        'rx-gradient-accent': 'linear-gradient(135deg, #34d399 0%, #10b981 100%)',
        'rx-gradient-card': 'linear-gradient(135deg, rgba(30,58,95,0.4) 0%, rgba(12,25,41,0.4) 100%)',
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
