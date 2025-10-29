'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { Home, Shield, MessageSquare, BarChart } from 'lucide-react';

interface NavItem {
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
  testId: string;
}

const navItems: NavItem[] = [
  { label: 'Dashboard', href: '/', icon: Home, testId: 'bottom-nav-dashboard' },
  { label: 'Betanet', href: '/betanet', icon: Shield, testId: 'bottom-nav-betanet' },
  { label: 'BitChat', href: '/bitchat', icon: MessageSquare, testId: 'bottom-nav-bitchat' },
  { label: 'Benchmarks', href: '/benchmarks', icon: BarChart, testId: 'bottom-nav-benchmarks' },
];

export function BottomNavigation() {
  const pathname = usePathname();

  return (
    <nav
      data-testid="bottom-navigation"
      className="fixed bottom-0 left-0 right-0 z-50 bg-gray-900 border-t border-gray-800 md:hidden"
      aria-label="Mobile navigation"
    >
      <div className="flex justify-around items-center h-16">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = pathname === item.href;

          return (
            <Link
              key={item.href}
              href={item.href}
              data-testid={item.testId}
              className={`flex flex-col items-center justify-center flex-1 h-full space-y-1 transition-colors ${
                isActive
                  ? 'text-blue-500'
                  : 'text-gray-400 hover:text-gray-200'
              }`}
              aria-current={isActive ? 'page' : undefined}
            >
              <Icon className="w-6 h-6" aria-hidden="true" />
              <span className="text-xs font-medium">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
