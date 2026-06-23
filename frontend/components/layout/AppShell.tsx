import { Sidebar } from "./Sidebar";

export function AppShell({
  children,
  title,
  subtitle,
  fillHeight = false,
}: {
  children: React.ReactNode;
  title?: string;
  subtitle?: string;
  fillHeight?: boolean;
}) {
  return (
    <div className="app-shell">
      <Sidebar />
      <main className={`main-content${fillHeight ? " main-content-fill" : ""}`}>
        {(title || subtitle) && (
          <header className="page-header">
            {title ? <h1>{title}</h1> : null}
            {subtitle ? <p>{subtitle}</p> : null}
          </header>
        )}
        {children}
      </main>
    </div>
  );
}
