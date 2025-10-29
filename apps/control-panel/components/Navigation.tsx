'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useState, useEffect, useRef } from 'react';
import { WebSocketStatus } from './WebSocketStatus';

export function Navigation() {
  const pathname = usePathname();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement>(null);
  const backdropRef = useRef<HTMLDivElement>(null);

  const links = [
    { href: '/', label: 'Dashboard', icon: '📊' },
    { href: '/betanet', label: 'Betanet', icon: '🔒' },
    { href: '/bitchat', label: 'BitChat', icon: '💬' },
    { href: '/benchmarks', label: 'Benchmarks', icon: '⚡' },
    { href: '/quality', label: 'Quality', icon: '✅' },
  ];

  // Close menu on route change
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [pathname]);

  // Handle swipe gestures for closing drawer
  useEffect(() => {
    if (!isMobileMenuOpen || !drawerRef.current) return;

    let startX = 0;
    let startY = 0;
    let isDragging = false;

    const handleTouchStart = (e: TouchEvent) => {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
      isDragging = true;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!isDragging) return;

      const currentX = e.touches[0].clientX;
      const currentY = e.touches[0].clientY;
      const diffX = currentX - startX;
      const diffY = Math.abs(currentY - startY);

      // Only handle horizontal swipes (not vertical scrolling)
      if (diffY < 50 && drawerRef.current) {
        // For right-side drawer, swipe right to close
        if (diffX > 0) {
          const translateX = Math.min(diffX, drawerRef.current.offsetWidth);
          drawerRef.current.style.transform = `translateX(${translateX}px)`;
        }
      }
    };

    const handleTouchEnd = (e: TouchEvent) => {
      if (!isDragging || !drawerRef.current) return;

      const endX = e.changedTouches[0].clientX;
      const diffX = endX - startX;

      // Reset transform
      drawerRef.current.style.transform = '';

      // If swiped right more than 100px, close the drawer
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
      if (drawer) {
        drawer.removeEventListener('touchstart', handleTouchStart);
        drawer.removeEventListener('touchmove', handleTouchMove);
        drawer.removeEventListener('touchend', handleTouchEnd);
      }
    };
  }, [isMobileMenuOpen]);

  // Close on ESC key and handle focus trap
  useEffect(() => {
    if (!isMobileMenuOpen) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsMobileMenuOpen(false);
      }
    };

    // Trap focus within drawer
    const handleTab = (e: KeyboardEvent) => {
      if (e.key !== 'Tab' || !drawerRef.current) return;

      const focusableElements = drawerRef.current.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0] as HTMLElement;
      const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          lastElement?.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastElement) {
          firstElement?.focus();
          e.preventDefault();
        }
      }
    };

    document.addEventListener('keydown', handleEscape);
    document.addEventListener('keydown', handleTab);

    // Focus first element when drawer opens
    if (drawerRef.current) {
      const firstFocusable = drawerRef.current.querySelector(
        'button, [href]'
      ) as HTMLElement;
      firstFocusable?.focus();
    }

    return () => {
      document.removeEventListener('keydown', handleEscape);
      document.removeEventListener('keydown', handleTab);
    };
  }, [isMobileMenuOpen]);

  // Prevent body scroll when drawer is open
  useEffect(() => {
    if (isMobileMenuOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }

    return () => {
      document.body.style.overflow = '';
    };
  }, [isMobileMenuOpen]);

  return (
    <nav className="glass-dark border-b border-white/10" data-testid="main-nav">
      <div className="container mx-auto px-4">
        <div className="flex items-center justify-between h-16">
          {/* Logo */}
          <div className="flex items-center space-x-2">
            <div className="text-2xl">☁️</div>
            <span className="font-bold text-xl bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
              Fog Compute
            </span>
          </div>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center space-x-1" data-testid="desktop-nav">
            {links.map((link) => {
              const isActive = pathname === link.href;
              return (
                <Link
                  key={link.href}
                  href={link.href}
                  className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-colors ${
                    isActive
                      ? 'bg-fog-cyan/20 text-fog-cyan'
                      : 'text-gray-400 hover:text-white hover:bg-white/5'
                  }`}
                >
                  <span>{link.icon}</span>
                  <span className="hidden sm:inline">{link.label}</span>
                </Link>
              );
            })}
          </div>

          {/* System Status */}
          <div className="hidden md:flex items-center space-x-4">
            <WebSocketStatus />
          </div>

          {/* Mobile Menu Button */}
          <button
            data-testid="mobile-menu-button"
            className="md:hidden p-2 text-gray-400 hover:text-white transition-colors"
            onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)}
            aria-label="Menu"
            aria-expanded={isMobileMenuOpen}
            aria-controls="mobile-menu-drawer"
          >
            {isMobileMenuOpen ? (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              </svg>
            )}
          </button>
        </div>
      </div>

      {/* Mobile Menu Overlay */}
      {isMobileMenuOpen && (
        <div
          ref={backdropRef}
          data-testid="mobile-menu-backdrop"
          className="md:hidden fixed inset-0 bg-black/50 z-40 transition-opacity duration-300"
          onClick={() => setIsMobileMenuOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Mobile Menu Drawer */}
      <div
        ref={drawerRef}
        id="mobile-menu-drawer"
        data-testid="mobile-menu-drawer"
        role="navigation"
        aria-label="Mobile navigation menu"
        aria-hidden={!isMobileMenuOpen}
        className={`md:hidden fixed top-0 right-0 bottom-0 w-80 max-w-[85vw] glass-dark border-l border-white/10 z-50 transform transition-transform duration-300 ease-in-out overflow-y-auto ${
          isMobileMenuOpen ? 'translate-x-0' : 'translate-x-full'
        }`}
      >
        {/* Drawer Header */}
        <div className="flex items-center justify-between h-16 px-4 border-b border-white/10 sticky top-0 glass-dark z-10">
          <div className="flex items-center space-x-2">
            <div className="text-xl">☁️</div>
            <span className="font-bold text-lg bg-gradient-to-r from-fog-cyan to-fog-purple bg-clip-text text-transparent">
              Menu
            </span>
          </div>
          <button
            onClick={() => setIsMobileMenuOpen(false)}
            className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-white/5"
            aria-label="Close menu"
            data-testid="mobile-menu-close"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Navigation Links */}
        <div className="p-4 space-y-2">
          {links.map((link) => {
            const isActive = pathname === link.href;
            return (
              <Link
                key={link.href}
                href={link.href}
                data-testid={`mobile-menu-link-${link.label.toLowerCase()}`}
                data-route={link.href}
                onClick={() => setIsMobileMenuOpen(false)}
                className={`flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors min-h-[44px] ${
                  isActive
                    ? 'bg-fog-cyan/20 text-fog-cyan'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <span className="text-xl">{link.icon}</span>
                <span className="font-medium">{link.label}</span>
              </Link>
            );
          })}

          {/* Mobile System Status */}
          <div className="pt-4 mt-4 border-t border-white/10">
            <div className="px-4 py-2">
              <WebSocketStatus />
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
}
