'use client';

import type { ButtonHTMLAttributes, HTMLAttributes } from 'react';
import { createContext, useContext, useMemo, useState } from 'react';
import { cn } from '@/lib/utils';

interface TabsContextValue {
  value: string;
  setValue: (value: string) => void;
}

const TabsContext = createContext<TabsContextValue | null>(null);

function useTabsContext(componentName: string) {
  const context = useContext(TabsContext);

  if (!context) {
    throw new Error(`${componentName} must be used within Tabs`);
  }

  return context;
}

interface TabsProps extends HTMLAttributes<HTMLDivElement> {
  defaultValue?: string;
  value?: string;
  onValueChange?: (value: string) => void;
}

export function Tabs({
  className = '',
  defaultValue = '',
  value,
  onValueChange,
  ...props
}: TabsProps) {
  const [internalValue, setInternalValue] = useState(defaultValue);
  const currentValue = value ?? internalValue;

  const contextValue = useMemo<TabsContextValue>(
    () => ({
      value: currentValue,
      setValue: (nextValue: string) => {
        if (value === undefined) {
          setInternalValue(nextValue);
        }
        onValueChange?.(nextValue);
      },
    }),
    [currentValue, onValueChange, value]
  );

  return (
    <TabsContext.Provider value={contextValue}>
      <div className={cn('space-y-4', className)} {...props} />
    </TabsContext.Provider>
  );
}

export function TabsList({ className = '', ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="tablist"
      className={cn(
        'inline-flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-white/5 p-1',
        className
      )}
      {...props}
    />
  );
}

interface TabsTriggerProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  value: string;
}

export function TabsTrigger({
  className = '',
  onClick,
  type = 'button',
  value,
  ...props
}: TabsTriggerProps) {
  const tabs = useTabsContext('TabsTrigger');
  const selected = tabs.value === value;

  return (
    <button
      type={type}
      role="tab"
      aria-selected={selected}
      data-state={selected ? 'active' : 'inactive'}
      className={cn(
        'min-h-[40px] rounded px-3 py-2 text-sm font-medium transition-colors',
        selected
          ? 'bg-fog-cyan text-black'
          : 'text-gray-300 hover:bg-white/10 hover:text-white',
        className
      )}
      onClick={(event) => {
        onClick?.(event);
        if (!event.defaultPrevented) {
          tabs.setValue(value);
        }
      }}
      {...props}
    />
  );
}

interface TabsContentProps extends HTMLAttributes<HTMLDivElement> {
  value: string;
}

export function TabsContent({ className = '', value, ...props }: TabsContentProps) {
  const tabs = useTabsContext('TabsContent');

  if (tabs.value !== value) {
    return null;
  }

  return <div role="tabpanel" className={cn('outline-none', className)} {...props} />;
}
