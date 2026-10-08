/**
 * Container card for content groups — listings, info panels, settings.
 * @startingPoint section="Components" subtitle="Shadowed content card" viewport="700x160"
 */
export interface CardProps {
  children: React.ReactNode;
  padding?: string;
  radius?: string;
  shadow?: string;
  onClick?: () => void;
  style?: React.CSSProperties;
}
export function Card(props: CardProps): React.ReactElement;
