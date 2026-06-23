"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/lib/auth";

const NAV = [
  { href: "/", label: "首页" },
  { href: "/courses", label: "课程" },
  { href: "/learn", label: "对话" },
  { href: "/path", label: "路径" },
  { href: "/practice", label: "练习" },
  { href: "/resources", label: "资源" }
];

export function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, memoryPath } = useAuth();

  if (pathname === "/login") return null;

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div>
          <strong>学习平台</strong>
          <span>Learning Dashboard</span>
        </div>
      </div>

      {user ? (
        <div className="sidebar-user">
          <div>
            <strong>{user.name}</strong>
            <span>{user.id}</span>
          </div>
        </div>
      ) : null}

      <nav className="sidebar-nav">
        {NAV.map(({ href, label }) => {
          const active =
            href === "/"
              ? pathname === "/"
              : pathname === href || pathname.startsWith(`${href}/`) || (href.startsWith("/courses") && pathname.startsWith("/courses"));
          return (
            <Link key={href} href={href} className={active ? "nav-item active" : "nav-item"}>
              <span className={active ? "nav-dot nav-dot-active" : "nav-dot"} />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        {user ? (
          <>
            <span className="memory-path" title={memoryPath("memory")}>
              memory: users/{user.id}/
            </span>
            <button
              type="button"
              className="logout-btn"
              onClick={() => {
                logout();
                router.push("/login");
              }}
            >
              退出登录
            </button>
          </>
        ) : null}
      </div>
    </aside>
  );
}
