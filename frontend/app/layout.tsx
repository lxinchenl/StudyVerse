import "./globals.css";
import type { Metadata } from "next";

import { AuthProvider } from "@/lib/auth";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { UiPreferencesInit } from "@/components/layout/UiPreferencesInit";

export const metadata: Metadata = {
  title: "EduAgent · 个性化学习多智能体系统",
  description: "基于大模型的个性化资源生成与学习多智能体系统"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>
        <AuthProvider>
          <UiPreferencesInit />
          <AuthGuard>{children}</AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
