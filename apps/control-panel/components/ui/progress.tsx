import * as React from "react";

import { cn } from "@/lib/utils";

export interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
}

export function Progress({ className, value = 0, ...props }: ProgressProps) {
  const boundedValue = Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));

  return (
    <div
      className={cn("relative h-4 w-full overflow-hidden rounded-full bg-white/10", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={boundedValue}
      {...props}
    >
      <div
        className="h-full w-full flex-1 bg-fog-cyan transition-transform"
        style={{ transform: `translateX(-${100 - boundedValue}%)` }}
      />
    </div>
  );
}
