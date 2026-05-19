import type { Metadata } from 'next';
import './globals.css';
import { Toaster } from 'react-hot-toast';
import { ResponsiveRuntime } from '@/components/ResponsiveRuntime';
import { AppShell } from '@/components/AppShell';

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
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
