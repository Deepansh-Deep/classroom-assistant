import type { Config } from "tailwindcss";
export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "sans-serif"], display: ["'Space Grotesk'", "Inter", "sans-serif"] },
      colors: { ink: { 950: "#0a0b10", 900: "#11131a", 800: "#181b24", 700: "#232734", 500: "#6b7186", 300: "#a9aec0" } },
      keyframes: { rise: { from: { opacity: "0", transform: "translateY(12px)" }, to: { opacity: "1", transform: "none" } } },
      animation: { rise: "rise .5s cubic-bezier(.2,.8,.2,1) both" },
    },
  },
} satisfies Config;
