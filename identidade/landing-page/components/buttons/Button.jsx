import React from 'react';
export function Button({ children, variant = 'primary', size = 'md', disabled = false, icon, onClick, style, ...rest }) {
  const base = {
    display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: '6px',
    fontFamily: 'var(--font-body)', fontWeight: 600, cursor: disabled ? 'not-allowed' : 'pointer',
    border: 'none', transition: 'all 150ms ease', opacity: disabled ? 0.5 : 1,
    lineHeight: 1, whiteSpace: 'nowrap',
  };
  const sizes = {
    sm: { fontSize: '13px', padding: '8px 14px', borderRadius: 'var(--radius-md)' },
    md: { fontSize: '14px', padding: '10px 20px', borderRadius: 'var(--radius-md)' },
    lg: { fontSize: '16px', padding: '14px 28px', borderRadius: 'var(--radius-md)' },
  };
  const variants = {
    primary: { background: 'var(--color-teal-700)', color: '#fff' },
    secondary: { background: 'var(--color-orange-700)', color: '#fff' },
    ghost: { background: 'transparent', color: 'var(--color-teal-700)', border: '1.5px solid var(--color-teal-700)' },
    outline: { background: 'transparent', color: 'var(--color-slate-700)', border: '1.5px solid var(--color-slate-300)' },
    gold: { background: 'var(--color-gold-400)', color: 'var(--color-slate-900)' },
    dark: { background: 'var(--color-black)', color: '#fff' },
  };
  return React.createElement('button', {
    onClick, disabled, style: { ...base, ...sizes[size], ...variants[variant], ...style }, ...rest
  }, icon, children);
}
