/**
 * Text input field with label and validation.
 * @startingPoint section="Components" subtitle="Labeled text input" viewport="700x160"
 */
export interface InputProps {
  label?: string;
  placeholder?: string;
  value?: string;
  onChange?: (value: string) => void;
  type?: string;
  error?: string;
  disabled?: boolean;
  style?: React.CSSProperties;
}
export function Input(props: InputProps): React.ReactElement;
