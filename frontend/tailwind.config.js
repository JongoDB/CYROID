// frontend/tailwind.config.js
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          200: '#bfdbfe',
          300: '#93c5fd',
          400: '#60a5fa',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          800: '#1e40af',
          900: '#1e3a8a',
        },
      },
      animation: {
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'pulse-once': 'pulseOnce 0.5s ease-in-out',
        'status-pulse': 'statusPulse 1s ease-in-out',
      },
      keyframes: {
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' },
        },
        pulseOnce: {
          '0%': { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(59, 130, 246, 0.5)' },
          '50%': { transform: 'scale(1.05)', boxShadow: '0 0 0 10px rgba(59, 130, 246, 0)' },
          '100%': { transform: 'scale(1)', boxShadow: '0 0 0 0 rgba(59, 130, 246, 0)' },
        },
        statusPulse: {
          '0%': { opacity: '1' },
          '50%': { opacity: '0.5' },
          '100%': { opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/typography'),
  ],
}
