/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
        },
        // Additive only — used for the citizen-facing "premium civic"
        // header/typography accents. Does not replace `brand` (teal),
        // which stays the primary action color everywhere, staff
        // dashboard included.
        navy: {
          50: "#f5f7fa",
          100: "#e9edf3",
          200: "#cbd5e3",
          300: "#94a7c4",
          400: "#5b76a3",
          500: "#3a5580",
          600: "#2a4066",
          700: "#1f3252",
          800: "#162540",
          900: "#0f1a2e",
        },
      },
    },
  },
  plugins: [],
};
