import type { HTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: 'default' | 'secondary' | 'outline' | 'destructive';
}

const variants: Record<NonNullable<BadgeProps['variant']>, string> = {
  default: 'bg-fog-cyan/20 text-fog-cyan',
  secondary: 'bg-white/10 text-gray-200',
  outline: 'border border-white/15 bg-transparent text-gray-200',
  destructive: 'bg-red-500/20 text-red-300',
};

export function Badge({ className = '', variant = 'default', ...props }: BadgeProps) {
  return (
    <span
      className={cn('inline-flex items-center rounded px-2 py-1 text-xs font-medium', variants[variant], className)}
      {...props}
    />
  );
}
