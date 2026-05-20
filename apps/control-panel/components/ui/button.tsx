import type { ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'outline' | 'ghost' | 'secondary' | 'destructive';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

const variants: Record<NonNullable<ButtonProps['variant']>, string> = {
  default: 'bg-fog-cyan text-black hover:bg-fog-cyan/80',
  outline: 'border border-white/15 bg-white/5 text-white hover:bg-white/10',
  ghost: 'bg-transparent text-gray-300 hover:bg-white/10 hover:text-white',
  secondary: 'bg-white/10 text-white hover:bg-white/20',
  destructive: 'bg-red-500 text-white hover:bg-red-600',
};

const sizes: Record<NonNullable<ButtonProps['size']>, string> = {
  default: 'min-h-[44px] px-4 py-2',
  sm: 'min-h-[36px] px-3 py-1.5 text-sm',
  lg: 'min-h-[48px] px-6 py-3',
  icon: 'h-10 w-10 p-0',
};

export function Button({
  className = '',
  variant = 'default',
  size = 'default',
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-colors disabled:pointer-events-none disabled:opacity-50',
        variants[variant],
        sizes[size],
        className
      )}
      {...props}
    />
  );
}
