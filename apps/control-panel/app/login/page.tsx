import type { Metadata } from 'next';
import { Suspense } from 'react';
import { LoginForm } from '@/components/auth/LoginForm';

export const metadata: Metadata = {
  title: 'Login | Fog Compute',
};

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <section className="mx-auto w-full max-w-md rounded-lg border border-white/10 bg-white/5 p-6 shadow-xl">
          <h1 className="text-3xl font-semibold">Login</h1>
        </section>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
