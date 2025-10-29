import type { Metadata } from 'next';
import './globals.css';
import { Navigation } from '@/components/Navigation';
import { Toaster } from 'react-hot-toast';
import { BottomNavigation } from '@/components/mobile/BottomNavigation';

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
    <html lang="en">
      <body className="antialiased">
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
        <div className="min-h-screen flex flex-col pb-16 md:pb-0" data-testid="main-layout">
          <Navigation />
          <main className="flex-1 container mx-auto px-4 py-6" data-testid="main-content">
            <div data-testid="main-grid">
              {children}
            </div>
          </main>
        </div>
        <BottomNavigation />
      </body>
    </html>
  );
}