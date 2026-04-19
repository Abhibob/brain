import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "primary": "#002d28",
        "primary-container": "#1a433e",
        "on-primary": "#ffffff",
        "on-primary-container": "#86afa8",
        "on-primary-fixed": "#00201d",
        "on-primary-fixed-variant": "#254d48",
        "primary-fixed": "#c0ebe4",
        "primary-fixed-dim": "#a5cfc8",
        "inverse-primary": "#a5cfc8",

        "secondary": "#52615f",
        "secondary-container": "#d5e6e2",
        "on-secondary": "#ffffff",
        "on-secondary-container": "#586765",
        "on-secondary-fixed": "#101e1c",
        "on-secondary-fixed-variant": "#3b4a47",
        "secondary-fixed": "#d5e6e2",
        "secondary-fixed-dim": "#b9cac6",

        "tertiary": "#3e1e12",
        "tertiary-container": "#583326",
        "on-tertiary": "#ffffff",
        "on-tertiary-container": "#cf9b8a",
        "on-tertiary-fixed": "#311308",
        "on-tertiary-fixed-variant": "#643d2f",
        "tertiary-fixed": "#ffdbcf",
        "tertiary-fixed-dim": "#f2baa7",

        "background": "#fbf9f5",
        "on-background": "#1b1c1a",
        "surface": "#fbf9f5",
        "surface-bright": "#fbf9f5",
        "surface-dim": "#dbdad6",
        "surface-tint": "#3e6560",
        "surface-variant": "#e4e2de",
        "on-surface": "#1b1c1a",
        "on-surface-variant": "#414847",
        "surface-container-lowest": "#ffffff",
        "surface-container-low": "#f5f3ef",
        "surface-container": "#efeeea",
        "surface-container-high": "#eae8e4",
        "surface-container-highest": "#e4e2de",

        "outline": "#717977",
        "outline-variant": "#c0c8c6",

        "error": "#ba1a1a",
        "error-container": "#ffdad6",
        "on-error": "#ffffff",
        "on-error-container": "#93000a",

        "inverse-surface": "#30312e",
        "inverse-on-surface": "#f2f0ed",
      },
      fontFamily: {
        headline: ["var(--font-headline)", "Newsreader", "serif"],
        body: ["var(--font-body)", "Public Sans", "sans-serif"],
        label: ["var(--font-body)", "Public Sans", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
