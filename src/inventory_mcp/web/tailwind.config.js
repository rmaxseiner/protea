/** @type {import('tailwindcss').Config} */

/*
 * Inventory MCP Web UI - Tailwind Configuration
 *
 * Color Scheme: King Protea
 * Inspired by the South African King Protea flower
 * - Dusty rose/coral petals
 * - Rich forest green foliage
 * - Creamy white center
 *
 * Layout: Sidebar Navigation (Layout A)
 */

module.exports = {
  content: [
    "./templates/**/*.html",
    "./static/**/*.js",
  ],
  theme: {
    extend: {
      colors: {
        // ===========================================
        // PROTEA - Rose/Coral Tones (Accent Colors)
        // ===========================================
        protea: {
          50:  '#fdf5f5',   // Palest pink - subtle backgrounds
          100: '#fae8e8',   // Light blush - hover states
          200: '#f5d0d0',   // Soft rose - borders, dividers
          300: '#ebb5b5',   // Dusty rose - tags, badges
          400: '#dc8f8f',   // Coral pink - warnings, medium emphasis
          500: '#c96b6b',   // Rose - match indicators, links
          600: '#a94f54',   // Deep coral - PRIMARY ACTIONS, active states
          700: '#8d3f43',   // Burgundy rose - hover on primary
          800: '#753538',   // Dark burgundy - pressed states
          900: '#632f31',   // Deep burgundy - text on light rose bg
          950: '#351617',   // Darkest burgundy - rare use
        },

        // ===========================================
        // FYNBOS - Forest Green Tones (Base Colors)
        // ===========================================
        fynbos: {
          50:  '#f4f7f4',   // Palest green - subtle backgrounds
          100: '#e4ebe4',   // Light sage - card backgrounds alt
          200: '#c9d7c9',   // Soft green - SECONDARY BUTTONS, borders
          300: '#a3b9a3',   // Sage - disabled states, low match
          400: '#7a967a',   // Forest sage - SECONDARY TEXT, medium match
          500: '#5c7a5c',   // Forest green - success states
          600: '#486248',   // Deep forest - icons
          700: '#3b4f3b',   // Dark forest - nav hover
          800: '#324032',   // Very dark green - SIDEBAR BACKGROUND
          900: '#2a352a',   // Deepest green - PRIMARY TEXT, sidebar dark
          950: '#151c15',   // Near black green - rare use
        },

        // ===========================================
        // CREAM - Warm Neutral Tones (Content Areas)
        // ===========================================
        cream: {
          light:   '#fefcf8',   // Lightest cream - CARD BACKGROUNDS
          DEFAULT: '#f7f2e8',   // Warm cream - CONTENT BACKGROUND
          dark:    '#e8dfc8',   // Deep cream - CARD BORDERS, dividers
        },
      },

      // ===========================================
      // SEMANTIC COLOR ALIASES
      // ===========================================
      backgroundColor: {
        'sidebar': '#324032',        // fynbos-800
        'sidebar-dark': '#2a352a',   // fynbos-900
        'content': '#f7f2e8',        // cream
        'card': '#fefcf8',           // cream-light
      },

      textColor: {
        'primary': '#2a352a',        // fynbos-900
        'secondary': '#5c7a5c',      // fynbos-500
        'muted': '#7a967a',          // fynbos-400
        'on-dark': '#fefcf8',        // cream-light
        'on-primary': '#fefcf8',     // cream-light (for protea-600 buttons)
      },

      borderColor: {
        'card': '#e8dfc8',           // cream-dark
        'input': '#c9d7c9',          // fynbos-200
        'focus': '#a94f54',          // protea-600
      },

      // ===========================================
      // COMPONENT PRESETS
      // ===========================================
      boxShadow: {
        'card': '0 1px 3px 0 rgb(50 64 50 / 0.1), 0 1px 2px -1px rgb(50 64 50 / 0.1)',
        'card-hover': '0 4px 6px -1px rgb(50 64 50 / 0.1), 0 2px 4px -2px rgb(50 64 50 / 0.1)',
        'panel': '0 10px 15px -3px rgb(50 64 50 / 0.1), 0 4px 6px -4px rgb(50 64 50 / 0.1)',
      },

      // ===========================================
      // TYPOGRAPHY
      // ===========================================
      fontFamily: {
        sans: ['system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },

      // ===========================================
      // SPACING & SIZING
      // ===========================================
      width: {
        'sidebar': '16rem',          // 256px
        'panel': '24rem',            // 384px
      },

      maxWidth: {
        'search': '42rem',           // 672px - search bar max width
        'content': '56rem',          // 896px - main content max width
      },
    },
  },
  plugins: [],
}
