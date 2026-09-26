"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Badge } from "./Badge";
import { Button } from "./Button";
import styles from "./AppShell.module.css";

export interface AppShellUser {
  userId: string;
  tenantId: string;
  businessUnitId: string | null;
  roles: string[];
}

export interface AppShellProps {
  user: AppShellUser;
  onLogout: () => void;
  children: ReactNode;
}

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/campaigns", label: "Campanhas" },
  { href: "/approvals", label: "Aprovações" },
  { href: "/brand-kit", label: "Brand Kit" },
  { href: "/connections", label: "Conexões" },
  { href: "/settings", label: "Configurações" },
] as const;

export function AppShell({ user, onLogout, children }: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className={styles.shell}>
      <a href="#campaia-main-content" className={styles.skipLink}>
        Ir para o conteúdo principal
      </a>
      <header className={styles.topbar}>
        <span className={styles.brand}>CampaIA</span>
        <div className={styles.topbarContext}>
          <Badge>{user.tenantId}</Badge>
          {user.businessUnitId ? <Badge tone="accent">{user.businessUnitId}</Badge> : null}
          <span className={styles.userId}>{user.userId}</span>
          <Button variant="secondary" onClick={onLogout} data-testid="logout-button">
            Sair
          </Button>
        </div>
      </header>
      <div className={styles.body}>
        <nav className={styles.sidebar} aria-label="Navegação principal">
          <ul className={styles.navList}>
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <li key={item.href}>
                  <Link
                    href={item.href}
                    className={active ? styles.navItemActive : styles.navItem}
                    aria-current={active ? "page" : undefined}
                  >
                    {item.label}
                  </Link>
                </li>
              );
            })}
          </ul>
        </nav>
        <main id="campaia-main-content" className={styles.main}>
          {children}
        </main>
      </div>
    </div>
  );
}
