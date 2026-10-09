/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        jp: ['"Zen Kaku Gothic New"', 'sans-serif'],
      },
      colors: {
        brand: { teal: '#138C87', neon: '#00F0FF' },
      },
    },
  },
  plugins: [],
}
