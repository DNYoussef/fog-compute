'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { FormEvent, useEffect, useMemo, useState } from 'react';

function passwordStrength(password: string) {
  let score = 0;
  if (password.length >= 8) score += 1;
  if (/[a-z]/.test(password)) score += 1;
  if (/[A-Z]/.test(password)) score += 1;
  if (/\d/.test(password)) score += 1;
  if (/[^A-Za-z0-9]/.test(password)) score += 1;

  if (score <= 2) return 'Weak';
  if (score <= 4) return 'Good';
  return 'Strong';
}

function isValidUsername(username: string) {
  return /^[A-Za-z0-9_]{3,32}$/.test(username);
}

export function RegisterForm() {
  const router = useRouter();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const strength = useMemo(() => passwordStrength(password), [password]);

  useEffect(() => {
    document.title = 'Register | Fog Compute';
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError('');
    setSuccess('');

    if (!isValidUsername(username)) {
      setError('Username must be 3-32 characters and use only letters, numbers, or underscores.');
      return;
    }

    if (passwordStrength(password) === 'Weak') {
      setError('Password must include uppercase, lowercase, and numbers.');
      return;
    }

    if (confirmPassword && confirmPassword !== password) {
      setError('Password confirmation must match.');
      return;
    }

    setIsSubmitting(true);

    try {
      const response = await fetch('/api/auth/register', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ username, email, password }),
      });
      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        setError(data.detail || 'User already exists or registration failed');
        return;
      }

      setSuccess('Registration successful. Redirecting to login.');
      router.push('/login');
    } catch {
      setError('Registration service is unavailable');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="mx-auto w-full max-w-md rounded-lg border border-white/10 bg-white/5 p-6 shadow-xl">
      <h1 className="text-3xl font-semibold">Register</h1>
      <p className="mt-2 text-sm text-gray-300">Create a Fog Compute operator account.</p>

      <form data-testid="register-form" className="mt-6 space-y-4" onSubmit={handleSubmit}>
        <div className="space-y-2">
          <label htmlFor="register-username" className="block text-sm font-medium">
            Username
          </label>
          <input
            id="register-username"
            name="username"
            data-testid="username-input"
            type="text"
            required
            minLength={3}
            maxLength={32}
            pattern="[A-Za-z0-9_]+"
            value={username}
            onChange={(event) => setUsername(event.target.value)}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-fog-cyan"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="register-email" className="block text-sm font-medium">
            Email
          </label>
          <input
            id="register-email"
            name="email"
            data-testid="email-input"
            type="email"
            required
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-fog-cyan"
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="register-password" className="block text-sm font-medium">
            Password
          </label>
          <input
            id="register-password"
            name="password"
            data-testid="password-input"
            type="password"
            required
            minLength={8}
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-fog-cyan"
          />
          {password ? (
            <p data-testid="password-strength" className="text-xs text-gray-300">
              {strength}
            </p>
          ) : null}
        </div>

        <div className="space-y-2">
          <label htmlFor="confirm-password" className="block text-sm font-medium">
            Confirm password
          </label>
          <input
            id="confirm-password"
            name="confirmPassword"
            data-testid="confirm-password-input"
            type="password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            className="w-full rounded-md border border-white/10 bg-black/30 px-3 py-2 text-white outline-none focus:border-fog-cyan"
          />
        </div>

        {error ? (
          <div data-testid="error-message" role="alert" className="rounded-md border border-red-500/40 bg-red-500/10 p-3 text-sm text-red-200">
            {error}
          </div>
        ) : null}

        {success ? (
          <div data-testid="success-message" className="rounded-md border border-green-500/40 bg-green-500/10 p-3 text-sm text-green-200">
            {success}
          </div>
        ) : null}

        <button
          data-testid="register-button"
          type="submit"
          disabled={isSubmitting}
          className="min-h-11 w-full rounded-md bg-fog-cyan px-4 py-2 font-semibold text-black transition hover:bg-fog-cyan/90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isSubmitting ? 'Creating account...' : 'Register'}
        </button>
      </form>

      <p className="mt-4 text-sm text-gray-300">
        Already have an account?{' '}
        <Link data-testid="login-link" href="/login" className="text-fog-cyan hover:underline">
          Login
        </Link>
      </p>
    </section>
  );
}
