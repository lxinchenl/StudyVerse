"use client";

import dynamic from "next/dynamic";
import { useCallback, useEffect, useState } from "react";

import { AppShell } from "@/components/layout/AppShell";
import { useAuth } from "@/lib/auth";
import { fetchResources } from "@/lib/api";
import type { GeneratedResource } from "@/lib/types";

const ResourceOffice = dynamic(
  () => import("@/components/studio/ResourceOffice").then((m) => m.ResourceOffice),
  { ssr: false, loading: () => <p className="muted" style={{ padding: 24 }}>加载办公室…</p> }
);

export default function ResourcesPage() {
  const { user } = useAuth();
  const [resources, setResources] = useState<GeneratedResource[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!user) return;
    setLoading(true);
    fetchResources(user.id)
      .then(setResources)
      .catch((e) => setError(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setLoading(false));
  }, [user]);

  const handleResourcesAdded = useCallback((created: GeneratedResource[]) => {
    setResources((prev) => [...created, ...prev]);
  }, []);

  const handleResourceDeleted = useCallback((resourceId: string) => {
    setResources((prev) => prev.filter((r) => r.id !== resourceId));
  }, []);

  return (
    <AppShell
      title="资源办公室"
      subtitle="Agent 团队协作生成学习资料 · 点击书柜查看文档库"
      fillHeight
    >
      {error ? <p className="muted resource-error">{error}</p> : null}
      {user ? (
        <ResourceOffice
          userId={user.id}
          resources={resources}
          onResourcesAdded={handleResourcesAdded}
          onResourceDeleted={handleResourceDeleted}
          loading={loading}
        />
      ) : null}
    </AppShell>
  );
}
