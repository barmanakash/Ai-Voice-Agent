/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#09090b",
          900: "#0e0e11",
          850: "#131317",
          800: "#18181d",
          700: "#222228",
          600: "#2e2e36",
          500: "#44444e",
        },
        accent: {
          DEFAULT: "#7c6cf0",
          hover: "#8b7df5",
          soft: "rgba(124, 108, 240, 0.14)",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      keyframes: {
        bounceDot: {
          "0%, 80%, 100%": { transform: "translateY(0)", opacity: "0.4" },
          "40%": { transform: "translateY(-4px)", opacity: "1" },
        },
        fadeUp: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        pulseRing: {
          "0%": { boxShadow: "0 0 0 0 rgba(239,68,68,0.5)" },
          "100%": { boxShadow: "0 0 0 12px rgba(239,68,68,0)" },
        },
      },
      animation: {
        bounceDot: "bounceDot 1.2s infinite ease-in-out",
        fadeUp: "fadeUp 0.25s ease-out",
        pulseRing: "pulseRing 1.4s infinite",
      },
    },
  },
  plugins: [],
};
