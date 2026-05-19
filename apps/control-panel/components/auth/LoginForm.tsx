'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, useEffect, useState } from 'react';

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [error, setError] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    document.title = 'Login | Fog Compute';
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setIsSubmitting(true);

    try {
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, password }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok || !data.access_token) {
        setError(data.detail || 'Invalid username or password');
        return;
      }

      window.localStorage.setItem('access_token', data.access_token);
      window.localStorage.setItem('token_type', data.token_type || 'bearer');

      if (rememberMe) {
        window.localStorage.setItem('remember_me', 'true');
      } else {
        window.localStorage.removeItem('remember_me');
      }

      const returnUrl = searchParams.get('return') || searchParams.get('redirect') || searchParams.get('next');
      router.push(returnUrl && returnUrl.startsWith('/') ? returnUrl : '/control-panel');
    } catch {
      setError('Authentication service is unavailable');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-md rounded-lg border border-white/10 bg-white/5 p-6 shadow-xl">
      <h1 className="text-3xl font-semibold">Login</h1>
      <p className="mt-2 text-sm text-gray-300">Access the Fog Compute control plane.</p>

      <form data-testid="login-form" className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label htmlFor="username" className="block text-sm font-medium">
            Username
          </label>
          <input
            id="username"
            name="username"
            data-testid="username-input"
            type="text"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-fog-cyan"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="password" className="block text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            name="password"
            data-testid="password-input"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-fog-cyan"
          />
        </div>

        <label className="flex items-center gap-2 text-sm text-gray-300">
          <input
            name="remember"
            data-testid="remember-me"
            type="checkbox"
            checked={rememberMe}
            onChange={(event) => setRememberMe(event.target.checked)}
          />
          Remember me
        </label>

        {error ? (
          <div data-testid="error-message" role="alert" className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        <button
          data-testid="login-button"
          type="submit"
          disabled={isSubmitting}
          className="min-h-11 w-full rounded-md bg-fog-cyan px-4 py-2 font-semibold text-black transition hover:bg-fog-cyan/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? 'Signing in...' : 'Login'}
        </button>
      </form>

      <div className="mt-4 flex items-center justify-between text-sm text-gray-300">
        <Link data-testid="register-link" href="/register" className="text-fog-cyan hover:underline">
          Register
        </Link>
        <Link data-testid="forgot-password-link" href="/login" className="text-gray-400 hover:text-white">
          Forgot password?
        </Link>
      </div>
    </section>
  );
}
