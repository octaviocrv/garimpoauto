import React from 'react';
export function Card({ children, padding = '16px', radius = 'var(--radius-md)', shadow = 'var(--shadow-sm)', style, onClick, ...rest }) {
  return React.createElement('div', {
    onClick,
    style: {
      background: '#fff', borderRadius: radius, boxShadow: shadow,
      border: '1px solid var(--border-default)', padding,
      cursor: onClick ? 'pointer' : 'default',
      transition: 'box-shadow 150ms ease', ...style
    }, ...rest
  }, children);
}
