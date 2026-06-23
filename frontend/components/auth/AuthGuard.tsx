"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useAuth } from "@/lib/auth";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (pathname === "/login") return;
    if (!user) router.replace("/login");
  }, [user, pathname, router]);

  if (pathname === "/login") return <>{children}</>;
  if (!user) return null;

  return <>{children}</>;
}
