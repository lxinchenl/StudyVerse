"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { AuthUI } from "@/components/ui/auth-ui";
import { useAuth } from "@/lib/auth";

export default function LoginPage() {
  const { user, login, register } = useAuth();
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  if (user) {
    router.replace("/");
    return null;
  }

  async function handleSignIn(email: string, password: string) {
    setLoading(true);
    setError(null);
    try {
      await login(email, password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleSignUp(payload: {
    name: string;
    email: string;
    password: string;
    major: string;
  }) {
    if (!payload.name) {
      setError("请输入姓名");
      return;
    }
    if (payload.password.length < 6) {
      setError("密码至少 6 位");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await register(payload.name, payload.email, payload.password, payload.major);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "注册失败");
    } finally {
      setLoading(false);
    }
  }

  return (
    <AuthUI
      loading={loading}
      error={error}
      onSignIn={handleSignIn}
      onSignUp={handleSignUp}
    />
  );
}
