import type { Metadata } from 'next';
import { LoginForm } from '@/components/auth/LoginForm';

export const metadata: Metadata = {
  title: 'Login | Fog Compute',
};

export default function LoginPage() {
  return <LoginForm />;
}
