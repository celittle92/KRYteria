/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Every colour resolves through a CSS variable so one token set drives both
      // themes. Never two stylesheets that drift.
      colors: {
        ground: "rgb(var(--ground) / <alpha-value>)",
        raised: "rgb(var(--raised) / <alpha-value>)",
        sunken: "rgb(var(--sunken) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        faint: "rgb(var(--faint) / <alpha-value>)",
        accent: "rgb(var(--accent) / <alpha-value>)",
        "accent-ink": "rgb(var(--accent-ink) / <alpha-value>)",
        support: "rgb(var(--support) / <alpha-value>)",
        contradict: "rgb(var(--contradict) / <alpha-value>)",
        complicate: "rgb(var(--complicate) / <alpha-value>)",
      },
      fontFamily: {
        // A system stack: no webfont request, nothing to fail on a slow connection,
        // and it reads as editorial rather than as a product.
        serif: ["Iowan Old Style", "Palatino Linotype", "Palatino", "Georgia", "serif"],
        sans: ["-apple-system", "BlinkMacSystemFont", "Segoe UI", "Inter", "Helvetica Neue", "Arial", "sans-serif"],
      },
      maxWidth: { reading: "68ch" },
      borderRadius: { card: "14px" },
      transitionDuration: { 400: "400ms" },
    },
  },
  plugins: [],
};
