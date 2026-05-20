import { motion, type MotionProps } from 'framer-motion';
import type { ReactNode, CSSProperties } from 'react';

type Direction = 'up' | 'down' | 'left' | 'right' | 'none';

interface FadeInProps extends MotionProps {
  children: ReactNode;
  delay?: number;
  duration?: number;
  direction?: Direction;
  className?: string;
  style?: CSSProperties;
}

const OFFSETS: Record<Direction, object> = {
  up:    { y: 14 },
  down:  { y: -14 },
  left:  { x: 14 },
  right: { x: -14 },
  none:  {},
};

/**
 * Wraps children in a smooth Framer Motion fade-in animation.
 * Direction controls which axis the element slides in from.
 */
export function FadeIn({
  children,
  delay = 0,
  duration = 0.35,
  direction = 'up',
  className,
  style,
  ...motionProps
}: FadeInProps) {
  return (
    <motion.div
      className={className}
      style={style}
      initial={{ opacity: 0, ...OFFSETS[direction] }}
      animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration, delay, ease: [0.22, 1, 0.36, 1] }}
      {...motionProps}
    >
      {children}
    </motion.div>
  );
}
