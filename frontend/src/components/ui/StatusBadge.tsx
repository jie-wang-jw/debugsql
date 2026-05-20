import './StatusBadge.css';

type BadgeVariant = 'blue' | 'cyan' | 'green' | 'orange' | 'red' | 'purple' | 'gray';

interface StatusBadgeProps {
  label: string;
  variant?: BadgeVariant;
  dot?: boolean;
  size?: 'xs' | 'sm' | 'md';
  className?: string;
}

/** Compact status badge / chip used throughout the UI. */
export function StatusBadge({
  label,
  variant = 'blue',
  dot = false,
  size = 'sm',
  className = '',
}: StatusBadgeProps) {
  return (
    <span className={`sbadge sbadge--${variant} sbadge--${size} ${className}`}>
      {dot && <span className="sbadge__dot" />}
      {label}
    </span>
  );
}
