import React from 'react';
export function Badge({ children, variant = 'default', size = 'md', style, ...rest }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', gap: '4px',
    fontFamily: 'var(--font-body)', fontWeight: 600, borderRadius: '999px',
    lineHeight: 1, whiteSpace: 'nowrap',
  };
  const sizes = {
    sm: { fontSize: '10px', padding: '3px 8px' },
    md: { fontSize: '11px', padding: '4px 10px' },
    lg: { fontSize: '12px', padding: '5px 12px' },
  };
  const variants = {
    default: { background: 'var(--color-slate-100)', color: 'var(--color-slate-600)' },
    teal: { background: 'var(--color-teal-50)', color: 'var(--color-teal-700)' },
    secondary: { background: 'var(--color-stone-100)', color: 'var(--color-black)' },
    gold: { background: '#FEF3C7', color: 'var(--color-gold-600)' },
    success: { background: 'var(--color-teal-50)', color: 'var(--color-teal-700)' },
    error: { background: '#FEF2F2', color: '#DC2626' },
    dark: { background: 'var(--color-slate-900)', color: '#fff' },
  };
  return React.createElement('span', {
    style: { ...base, ...sizes[size], ...variants[variant], ...style }, ...rest
  }, children);
}
