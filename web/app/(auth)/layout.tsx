// Auth layout — minimal, no sidebar. Used by /login.
export default function AuthLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return <>{children}</>;
}
