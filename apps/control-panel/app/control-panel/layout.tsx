import { AuthGate } from '@/components/auth/AuthGate';

export default function ControlPanelLayout({ children }: { children: React.ReactNode }) {
  return <AuthGate>{children}</AuthGate>;
}
