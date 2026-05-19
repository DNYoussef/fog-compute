import type { Metadata } from 'next';
import './globals.css';
import { Navigation } from '@/components/Navigation';
import { Toaster } from 'react-hot-toast';
import { BottomNavigation } from '@/components/mobile/BottomNavigation';
import { ResponsiveRuntime } from '@/components/ResponsiveRuntime';

export const metadata: Metadata = {
  title: 'Fog Compute Control Panel',
  description: 'Unified control panel for Fog Compute platform - Betanet, BitChat, and Benchmarks',
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" dir="ltr">
      <body className="antialiased mobile tablet desktop">
        <ResponsiveRuntime />
        <Toaster
          position="top-right"
          toastOptions={{
            style: {
              background: '#0a0e27',
              color: '#fff',
              border: '1px solid rgba(255, 255, 255, 0.1)',
            },
            success: {
              iconTheme: {
                primary: '#10b981',
                secondary: '#fff',
              },
            },
            error: {
              iconTheme: {
                primary: '#ef4444',
                secondary: '#fff',
              },
            },
          }}
        />
        <div className="min-h-screen flex flex-col pb-16 md:pb-0" data-testid="main-layout" data-orientation="portrait">
          <Navigation />
          <div className="flex flex-1">
            <aside
              data-testid="sidebar"
              className="hidden w-14 flex-shrink-0 border-r border-white/10 bg-black/20 md:flex xl:w-16"
              aria-label="Context rail"
            />
            <main className="flex-1 container mx-auto px-4 py-6" data-testid="main-content">
              <div className="grid gap-6" data-testid="main-grid">
                {children}
              </div>
            </main>
          </div>
        </div>
        <BottomNavigation />
      </body>
    </html>
  );
}
