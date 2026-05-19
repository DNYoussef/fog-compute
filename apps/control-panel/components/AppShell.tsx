'use client';

import { usePathname } from 'next/navigation';
import type { ReactNode } from 'react';
import { BottomNavigation } from '@/components/mobile/BottomNavigation';
import { Navigation } from '@/components/Navigation';

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const isAuthRoute = pathname === '/login' || pathname === '/register';
  const mainClassName = isAuthRoute
    ? 'flex-1 min-w-0 overflow-x-hidden px-4 py-6'
    : 'flex-1 min-w-0 overflow-x-hidden container mx-auto px-4 py-6';

  return (
    <>
      <div
        className={`min-h-screen flex flex-col ${isAuthRoute ? '' : 'pb-16 md:pb-0'}`}
        data-testid="main-layout"
        data-orientation="portrait"
      >
        {isAuthRoute ? null : <Navigation />}
        <div className="flex flex-1">
          {isAuthRoute ? null : (
            <aside
              data-testid="sidebar"
              className="hidden w-14 flex-shrink-0 border-r border-white/10 bg-black/20 md:flex xl:w-16"
              aria-label="Context rail"
            />
          )}
          <main
            className={mainClassName}
            data-testid="main-content"
          >
            <div className="grid min-w-0 gap-6" data-testid="main-grid">
              {children}
            </div>
          </main>
        </div>
      </div>
      {isAuthRoute ? null : <BottomNavigation />}
    </>
  );
}
