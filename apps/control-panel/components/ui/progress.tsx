import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface ProgressProps extends HTMLAttributes<HTMLDivElement> {
  value?: number;
}

export function Progress({ value = 0, className = '', ...props }: ProgressProps) {
  const boundedValue = Math.max(0, Math.min(100, value));

  return (
    <div
      className={cn('h-2 overflow-hidden rounded-full bg-white/10', className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={boundedValue}
      {...props}
    >
      <div className="h-full rounded-full bg-fog-cyan transition-all" style={{ width: `${boundedValue}%` }} />
    </div>
  );
}
