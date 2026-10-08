/**
 * Primary action button for Garimpo Auto UI.
 * Use for CTAs, form submissions, and navigation actions.
 * @startingPoint section="Components" subtitle="Teal/orange/ghost/outline button" viewport="700x200"
 */
export interface ButtonProps {
  children: React.ReactNode;
  /** @default "primary" */
  variant?: 'primary' | 'secondary' | 'ghost' | 'outline' | 'gold' | 'dark';
  /** @default "md" */
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  icon?: React.ReactNode;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export function Button(props: ButtonProps): React.ReactElement;
