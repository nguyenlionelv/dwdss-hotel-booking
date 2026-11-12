import tailwindcssAnimate from 'tailwindcss-animate';

/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class'],
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    container: {
      center: true,
      padding: '2rem',
      screens: {
        '2xl': '1440px',
      },
    },
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))',
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))',
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))',
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))',
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))',
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))',
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))',
        },
        chart: {
          1: 'rgb(var(--series-1-rgb) / <alpha-value>)',
          2: 'rgb(var(--series-2-rgb) / <alpha-value>)',
          3: 'rgb(var(--series-3-rgb) / <alpha-value>)',
          4: 'rgb(var(--series-4-rgb) / <alpha-value>)',
          5: 'rgb(var(--series-5-rgb) / <alpha-value>)',
        },
        // Lumina Analytics Semantic & Surface Tokens (Carbon Neutral Dark Mode Ready)
        surface: {
          workspace: 'rgb(var(--surface-workspace-rgb) / <alpha-value>)',
          primary: 'rgb(var(--surface-primary-rgb) / <alpha-value>)',
          subtle: 'rgb(var(--surface-subtle-rgb) / <alpha-value>)',
        },
        ink: {
          primary: 'rgb(var(--ink-primary-rgb) / <alpha-value>)',
          secondary: 'rgb(var(--ink-secondary-rgb) / <alpha-value>)',
          muted: 'rgb(var(--ink-muted-rgb) / <alpha-value>)',
        },
        divider: 'rgb(var(--divider-rgb) / <alpha-value>)',
        brand: {
          DEFAULT: 'rgb(var(--brand-rgb) / <alpha-value>)',
          hover: 'rgb(var(--brand-hover-rgb) / <alpha-value>)',
          subtle: 'rgb(var(--brand-subtle-rgb) / <alpha-value>)',
        },
        series: {
          1: 'rgb(var(--series-1-rgb) / <alpha-value>)',
          2: 'rgb(var(--series-2-rgb) / <alpha-value>)',
          3: 'rgb(var(--series-3-rgb) / <alpha-value>)',
          4: 'rgb(var(--series-4-rgb) / <alpha-value>)',
          5: 'rgb(var(--series-5-rgb) / <alpha-value>)',
        },
        status: {
          success: 'rgb(var(--status-success-rgb) / <alpha-value>)',
          warning: 'rgb(var(--status-warning-rgb) / <alpha-value>)',
          critical: 'rgb(var(--status-critical-rgb) / <alpha-value>)',
        },
      },
      borderRadius: {
        lg: '4px',
        md: '4px',
        sm: '2px',
        DEFAULT: '4px',
      },
      fontFamily: {
        sans: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        display: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        headline: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        body: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        label: ['Inter', '-apple-system', 'BlinkMacSystemFont', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' },
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' },
        },
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out',
      },
    },
  },
  plugins: [tailwindcssAnimate],
};
