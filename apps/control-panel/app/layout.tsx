import type { Metadata } from 'next';
import './globals.css';
import { Navigation } from '@/components/Navigation';

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
        <div className="min-h-screen flex flex-col">
          <Navigation />
          <main className="flex-1 container mx-auto px-4 py-6" data-testid="main-content">
            {children}
          </main>
        </div>
      </body>
    </html>
  );
}