/**
 * Status badge / tag for labels, counts, and categories.
 * @startingPoint section="Components" subtitle="Colored pill badge" viewport="700x100"
 */
export interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'teal' | 'orange' | 'gold' | 'success' | 'error' | 'dark';
  size?: 'sm' | 'md' | 'lg';
  style?: React.CSSProperties;
}
export function Badge(props: BadgeProps): React.ReactElement;
