"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import useAuth from "../hooks/useAuth";

export function AuthGuard({
  children,
  requireAuth = true,
}: {
  children: React.ReactNode;
  requireAuth?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const isAuthenticated = useAuth((state) => state.isAuthenticated);
  const isHydrated = useAuth((state) => state.isHydrated);

  useEffect(() => {
    useAuth.getState().hydrate();
  }, [pathname]);

  useEffect(() => {
    if (requireAuth && !isAuthenticated) {
      router.replace("/login");
    }

    if (!requireAuth && isAuthenticated) {
      router.replace("/dashboard");
    }
  }, [isAuthenticated, requireAuth, router]);

  if (!isHydrated) {
    return <div className="flex min-h-screen items-center justify-center bg-slate-50 text-sm text-slate-600">Loading workspace...</div>;
  }

  if (requireAuth && !isAuthenticated) {
    return null;
  }

  if (!requireAuth && isAuthenticated) {
    return null;
  }

  return <>{children}</>;
}
