module.exports = {
  darkMode: 'class',
  corePlugins: {
    preflight: false,
  },
  content: [
    './trees/templates/**/*.html',
    './trees/static/trees/**/*.js',
    './grove/templates/**/*.html',
    './grove_*/templates/**/*.html',
  ],
  theme: {
    extend: {
      colors: {
        forest: { 50: '#f0fdf4', 500: '#22c55e', 700: '#15803d', 900: '#14532d' },
        earth: { 50: '#faf7f2', 500: '#a3805a', 900: '#3d2f1f' },
        ink: { 50: '#f8fafc', 900: '#0f172a' },
      },
      fontFamily: {
        sans: ['Inter var', 'system-ui', 'sans-serif'],
        display: ['Plus Jakarta Sans', 'Inter', 'sans-serif'],
      },
      keyframes: {
        scaleIn: { from: { transform: 'scale(.96)', opacity: '0' }, to: { transform: 'scale(1)', opacity: '1' } },
        slideUp: { from: { transform: 'translateY(8px)', opacity: '0' }, to: { transform: 'translateY(0)', opacity: '1' } },
        pulseRing: { '0%': { boxShadow: '0 0 0 0 currentColor' }, '100%': { boxShadow: '0 0 0 8px transparent' } },
        navSlideIn: { from: { transform: 'translateX(1rem)', opacity: '0' }, to: { transform: 'translateX(0)', opacity: '1' } },
        iconRotate: { from: { transform: 'rotate(0) scale(1)' }, to: { transform: 'rotate(180deg) scale(.88)' } },
      },
      animation: {
        'scale-in': 'scaleIn 0.2s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
        'pulse-ring': 'pulseRing 0.6s ease-out',
        'nav-slide-in': 'navSlideIn 0.25s ease-out',
        'icon-rotate': 'iconRotate 0.3s ease-out',
      },
    },
  },
  plugins: [],
};
