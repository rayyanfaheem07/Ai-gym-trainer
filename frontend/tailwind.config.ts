import type { Config } from "tailwindcss";

export default {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "var(--background)",
        foreground: "var(--foreground)",
        neon: {
          green: "#10B981",
          cyan: "#06B6D4",
          amber: "#F59E0B",
          rose: "#F43F5E",
        },
      },
    },
  },
  plugins: [],
} satisfies Config;
