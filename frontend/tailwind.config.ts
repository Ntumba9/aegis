import type { Config } from "tailwindcss";

export default {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        charcoal: "#0b0d12",
        navy: "#0f1b2d",
        electric: "#3bd1ff",
      },
    },
  },
  plugins: [],
} satisfies Config;
