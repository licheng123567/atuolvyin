// tailwind v4: use the dedicated PostCSS package; the old `tailwindcss` plugin
// entry was removed.
export default {
  plugins: {
    "@tailwindcss/postcss": {},
    autoprefixer: {},
  },
}
