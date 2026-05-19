'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useEffect, useRef, useState } from 'react';
import { WebSocketStatus } from './WebSocketStatus';

const links = [
  { href: '/', label: 'Dashboard', icon: 'D', testId: 'dashboard-link' },
  { href: '/nodes', label: 'Nodes', icon: 'N', testId: 'nodes-link' },
  { href: '/tasks', label: 'Tasks', icon: 'T', testId: 'tasks-link' },
  { href: '/betanet', label: 'Betanet', icon: 'B', testId: 'betanet-link' },
  { href: '/bitchat', label: 'BitChat', icon: 'C', testId: 'bitchat-link' },
  { href: '/benchmarks', label: 'Benchmarks', icon: 'P', testId: 'benchmarks-link' },
  { href: '/quality', label: 'Quality', icon: 'Q', testId: 'quality-link' },
];

export function Navigation() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  useEffect(() => {
    if (!isMobileMenuOpen || !drawerRef.current) return;

    let startX = 0;
    let startY = 0;
    let isDragging = false;

    const handleTouchStart = (event: TouchEvent) => {
      startX = event.touches[0].clientX;
      startY = event.touches[0].clientY;
      isDragging = true;
    };

    const handleTouchMove = (event: TouchEvent) => {
      if (!isDragging || !drawerRef.current) return;

      const diffX = event.touches[0].clientX - startX;
      const diffY = Math.abs(event.touches[0].clientY - startY);

      if (diffY < 50 && diffX > 0) {
        drawerRef.current.style.transform = `translateX(${Math.min(diffX, drawerRef.current.offsetWidth)}px)`;
      }
    };

    const handleTouchEnd = (event: TouchEvent) => {
      if (!isDragging || !drawerRef.current) return;

      const diffX = event.changedTouches[0].clientX - startX;
      drawerRef.current.style.transform = '';

      if (diffX > 100) {
        setIsMobileMenuOpen(false);
      }
      isDragging = false;
    };

    const drawer = drawerRef.current;
    drawer.addEventListener('touchstart', handleTouchStart, { passive: true });
    drawer.addEventListener('touchmove', handleTouchMove, { passive: true });
    drawer.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      drawer.removeEventListener('touchstart', handleTouchStart);
      drawer.removeEventListener('touchmove', handleTouchMove);
      drawer.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isMobileMenuOpen]);

  useEffect(() => {
    document.body.style.overflow = isMobileMenuOpen ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileMenuOpen]);

  return (
    <nav className="glass-dark border-b border-white/10" data-testid="main-nav">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between min-h-16 py-2">
          <Link href="/" className="flex min-h-[44px] items-center space-x-2">
            <div className="flex h-9 w-9 items-center justify-center rounded bg-fog-cyan/20 text-fog-cyan font-bold">
              FC
            </div>
            <span className="font-bold text-xl bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
              Fog Compute
            </span>
          </Link>

          <div className="hidden md:flex items-center space-x-1" data-testid="desktop-nav">
            {links.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  data-testid={link.testId}
                  className={`flex min-h-[44px] items-center space-x-2 rounded-lg px-3 py-2 transition-colors ${
                    isActive
                      ? 'bg-fog-cyan/20 text-fog-cyan'
                      : 'text-gray-400 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <span className="flex h-6 w-6 items-center justify-center rounded bg-white/5 text-xs font-semibold">
                    {link.icon}
                  </span>
                  <span className="hidden lg:inline">{link.label}</span>
                </Link>
              );
            })}
          </div>

          <div className="hidden md:flex items-center space-x-4">
            <WebSocketStatus />
          </div>

          <div className="md:hidden" data-testid="mobile-menu">
            <button
              data-testid="mobile-menu-button"
              className="min-h-[44px] min-w-[44px] rounded-lg p-2 text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
              onClick={() => setIsMobileMenuOpen((open) => !open)}
              aria-label="Menu"
              aria-expanded={isMobileMenuOpen}
              aria-controls="mobile-menu-drawer"
            >
              <span className="sr-only">Menu</span>
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                {isMobileMenuOpen ? (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18 18 6M6 6l12 12" />
                ) : (
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                )}
              </svg>
            </button>
          </div>
        </div>
      </div>

      {isMobileMenuOpen && (
        <button
          data-testid="mobile-menu-backdrop"
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-label="Close menu backdrop"
        />
      )}

      <div
        ref={drawerRef}
        id="mobile-menu-drawer"
        data-testid="mobile-menu-drawer"
        role="navigation"
        aria-label="Mobile navigation menu"
        aria-hidden={!isMobileMenuOpen}
        className={`fixed bottom-0 right-0 top-0 z-50 w-80 max-w-[85vw] transform overflow-y-auto border-l border-white/10 glass-dark transition-transform duration-300 ease-in-out md:hidden ${
          isMobileMenuOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        <div data-testid="swipe-nav" className="flex h-full flex-col">
          <div className="sticky top-0 z-10 flex h-16 items-center justify-between border-b border-white/10 px-4 glass-dark">
            <span className="font-bold text-lg bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
              Menu
            </span>
            <button
              onClick={() => setIsMobileMenuOpen(false)}
              className="min-h-[44px] min-w-[44px] rounded-lg p-2 text-gray-400 transition-colors hover:bg-white/5 hover:text-white"
              aria-label="Close menu"
              data-testid="mobile-menu-close"
            >
              <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18 18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="space-y-2 p-4">
            {links.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  data-testid="menu-item"
                  data-route={link.href}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`flex min-h-[44px] items-center space-x-3 rounded-lg px-4 py-3 transition-colors ${
                    isActive
                      ? 'bg-fog-cyan/20 text-fog-cyan'
                      : 'text-gray-400 hover:bg-white/5 hover:text-white'
                  }`}
                >
                  <span className="flex h-7 w-7 items-center justify-center rounded bg-white/5 text-xs font-semibold">
                    {link.icon}
                  </span>
                  <span className="font-medium">{link.label}</span>
                </Link>
              );
            })}

            <div className="mt-4 border-t border-white/10 pt-4">
              <WebSocketStatus testId="mobile-ws-status" offlineTestId="mobile-offline-indicator" />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
