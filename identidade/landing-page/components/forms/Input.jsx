import React from 'react';
export function Input({ label, placeholder, value, onChange, type = 'text', error, disabled, style, ...rest }) {
  const [focused, setFocused] = React.useState(false);
  return React.createElement('div', { style: { display: 'flex', flexDirection: 'column', gap: '4px', ...style } },
    label && React.createElement('label', {
      style: { fontSize: '13px', fontWeight: 500, color: 'var(--color-slate-700)', fontFamily: 'var(--font-body)' }
    }, label),
    React.createElement('input', {
      type, placeholder, value, disabled,
      onChange: e => onChange && onChange(e.target.value),
      onFocus: () => setFocused(true), onBlur: () => setFocused(false),
      style: {
        fontFamily: 'var(--font-body)', fontSize: '14px', padding: '10px 12px',
        borderRadius: 'var(--radius-md)', border: error ? '1.5px solid #DC2626' : focused ? '1.5px solid var(--color-teal-500)' : '1.5px solid var(--color-slate-200)',
        background: disabled ? 'var(--color-slate-50)' : '#fff', color: 'var(--color-slate-800)',
        outline: 'none', transition: 'border-color 150ms ease', opacity: disabled ? 0.6 : 1,
      }, ...rest
    }),
    error && React.createElement('span', { style: { fontSize: '12px', color: '#DC2626', fontFamily: 'var(--font-body)' } }, error)
  );
}
