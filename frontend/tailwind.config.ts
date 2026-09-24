import type { Config } from "tailwindcss";

// Paleta y tokens del estilo DashStack (admin dashboard claro).
const config: Config = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: { DEFAULT: "#4880FF", hover: "#3a6fe0", soft: "#E9F0FF" },
        canvas: "#F5F6FA",
        ink: { DEFAULT: "#202224", muted: "#6B7280", faint: "#9CA3AF" },
        line: "#E6E8EE",
        success: "#00B69B",
        danger: "#EF3826",
        warning: "#FCA800",
        purple: "#8280FF",
      },
      fontFamily: {
        sans: ["var(--font-sans)", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "14px",
      },
      boxShadow: {
        card: "0 4px 24px rgba(15, 23, 42, 0.05)",
        soft: "0 2px 8px rgba(15, 23, 42, 0.04)",
      },
    },
  },
  plugins: [],
};

export default config;
