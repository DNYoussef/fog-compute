'use client';

import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';

type AuthState = 'checking' | 'authenticated' | 'unauthenticated';

let validatedToken: string | null = null;
let pendingValidation: { token: string; promise: Promise<boolean> } | null = null;

function validateToken(token: string) {
  if (validatedToken === token) {
    return Promise.resolve(true);
  }

  if (pendingValidation?.token === token) {
    return pendingValidation.promise;
  }

  const promise = fetch('/api/auth/me', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
    cache: 'no-store',
  })
    .then((response) => response.ok)
    .then((isValid) => {
      if (isValid) {
        validatedToken = token;
      }
      return isValid;
    })
    .catch(() => false)
    .finally(() => {
      if (pendingValidation?.token === token) {
        pendingValidation = null;
      }
    });

  pendingValidation = { token, promise };
  return promise;
}

export function AuthGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [state, setState] = useState<AuthState>('checking');

  useEffect(() => {
    let cancelled = false;

    const validateSession = async () => {
      const token = window.localStorage.getItem('access_token');

      if (!token) {
        validatedToken = null;
        setState('unauthenticated');
        router.replace(`/login?return=${encodeURIComponent(pathname)}`);
        return;
      }

      const isValid = await validateToken(token);

      if (cancelled) {
        return;
      }

      if (isValid) {
        setState('authenticated');
        return;
      }

      validatedToken = null;
      window.localStorage.removeItem('access_token');
      window.localStorage.removeItem('token_type');
      window.sessionStorage.clear();
      setState('unauthenticated');
      router.replace(`/login?return=${encodeURIComponent(pathname)}`);
    };

    validateSession();

    return () => {
      cancelled = true;
    };
  }, [pathname, router]);

  if (state === 'authenticated') {
    return <>{children}</>;
  }

  return (
    <section className="mx-auto max-w-xl rounded-lg border border-white/10 bg-white/5 p-6 text-center">
      <h1 className="text-2xl font-semibold">Authentication required</h1>
      <p className="mt-2 text-sm text-gray-300">
        Login is required to access this control panel route.
      </p>
    </section>
  );
}
