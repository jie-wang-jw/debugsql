// ================================================
// DebugSQL – SkeletonLoader  (Phase 6)
//
// Reusable shimmer skeleton for loading states.
// Renders a configurable set of animated lines.
//
// Usage:
//   <SkeletonLoader lines={[
//     { width: 'short',  size: 'lg' },
//     { width: 'long' },
//     { width: 'medium' },
//   ]} />
//
// TODO: Add block variant (for card-shaped skeletons)
// TODO: Add circle variant (for avatar placeholders)
// ================================================

import './SkeletonLoader.css';

type SkeletonWidth = 'short' | 'medium' | 'long' | 'full';
type SkeletonSize  = 'sm' | 'default' | 'lg';

interface SkeletonLine {
  width?: SkeletonWidth;
  size?:  SkeletonSize;
}

interface SkeletonLoaderProps {
  /** List of line descriptors — each produces one animated bar. */
  lines?: SkeletonLine[];
  /** Optional gap override (default uses gap from .skeleton class). */
  className?: string;
}

const DEFAULT_LINES: SkeletonLine[] = [
  { width: 'medium', size: 'lg' },
  { width: 'long' },
  { width: 'long' },
  { width: 'short' },
];

/**
 * SkeletonLoader – Shimmer placeholder for async content.
 * Drop-in replacement for any panel body while data loads.
 */
export function SkeletonLoader({
  lines = DEFAULT_LINES,
  className = '',
}: SkeletonLoaderProps) {
  return (
    <div
      className={`skeleton ${className}`}
      role="status"
      aria-label="Loading…"
      aria-busy="true"
    >
      {lines.map((line, i) => (
        <div
          key={i}
          className={[
            'skeleton__line',
            `skeleton__line--${line.width ?? 'full'}`,
            line.size && line.size !== 'default' ? `skeleton__line--${line.size}` : '',
          ].join(' ').trim()}
        />
      ))}
    </div>
  );
}
