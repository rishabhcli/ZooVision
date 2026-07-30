"use client";

import { AnimatePresence, MotionConfig, motion } from "motion/react";
import {
  BarChart3,
  ChevronDown,
  CircleUserRound,
  Monitor,
  Moon,
  Network,
  ScanLine,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { ReactNode, useEffect, useRef, useState } from "react";

type WorkspaceShellProps = {
  children: ReactNode;
  title: string;
  eyebrow: string;
};

const routeOptions = [
  { label: "Monitor", href: "/monitor", icon: Monitor },
  { label: "Node graph", href: "/graph", icon: Network },
  { label: "Analysis", href: "/analysis", icon: BarChart3 },
];

export function WorkspaceShell({
  children,
  title,
  eyebrow,
}: WorkspaceShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const profileRef = useRef<HTMLDivElement>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    function closeProfile(event: MouseEvent) {
      if (!profileRef.current?.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", closeProfile);
    return () => document.removeEventListener("mousedown", closeProfile);
  }, []);

  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ type: "spring", visualDuration: 0.3, bounce: 0.06 }}
    >
      <main className="app-frame">
        <section className="workspace">
          <header className="topbar">
            <div className="topbar-left">
              <button
                type="button"
                className="brand"
                onClick={() => router.push("/monitor")}
                aria-label="Open ZooVision monitor"
              >
                <span className="brand-mark" aria-hidden="true">
                  <ScanLine size={18} />
                </span>
                <span>ZooVision</span>
              </button>
              <span className="topbar-divider" />
              <div className="page-context">
                <span>{eyebrow}</span>
                <strong>{title}</strong>
              </div>
            </div>

            <nav className="route-tabs" aria-label="Workspace pages">
              {routeOptions.map((option) => {
                const Icon = option.icon;
                const isActive = pathname === option.href;
                return (
                  <button
                    key={option.href}
                    type="button"
                    className={isActive ? "active" : undefined}
                    aria-label={option.label}
                    aria-current={isActive ? "page" : undefined}
                    onClick={() => router.push(option.href)}
                  >
                    <Icon size={15} />
                    <span>{option.label}</span>
                    {isActive && (
                      <motion.i
                        className="route-tab-indicator"
                        layoutId="active-route-tab"
                      />
                    )}
                  </button>
                );
              })}
            </nav>

            <div className="topbar-right">
              <div className="shadow-badge">
                <ShieldCheck size={14} />
                Shadow mode
              </div>
              <div className="shift-status">
                <Moon size={15} />
                <span>Night shift</span>
                <strong>05:42</strong>
              </div>
              <div className="profile-menu" ref={profileRef}>
                <button
                  type="button"
                  className="profile-trigger"
                  onClick={() => setProfileOpen((current) => !current)}
                  aria-expanded={profileOpen}
                  aria-haspopup="menu"
                >
                  <span className="profile-avatar">MC</span>
                  <span className="profile-copy">
                    <strong>Maria Chen</strong>
                    <small>Night keeper</small>
                  </span>
                  <ChevronDown size={15} />
                </button>
                <AnimatePresence>
                  {profileOpen && (
                    <motion.div
                      className="dropdown-menu profile-dropdown"
                      role="menu"
                      initial={{ opacity: 0, y: -6, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -6, scale: 0.98 }}
                    >
                      <div className="profile-summary">
                        <span className="profile-avatar large">
                          <CircleUserRound size={18} />
                        </span>
                        <div>
                          <strong>Maria Chen</strong>
                          <span>Keeper · North habitat</span>
                        </div>
                      </div>
                      <div className="menu-separator" />
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setProfileOpen(false);
                          setSettingsOpen(true);
                        }}
                      >
                        <Settings size={16} />
                        <span>Workspace settings</span>
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </div>
          </header>

          <div className="workspace-content">{children}</div>
          <footer className="safety-footer">
            Welfare support only
            <span>·</span>
            No diagnosis or treatment
            <span>·</span>
            Verify evidence before action
          </footer>
        </section>
      </main>

      <AnimatePresence>
        {settingsOpen && (
          <motion.div
            className="modal-backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onMouseDown={(event) => {
              if (event.currentTarget === event.target) setSettingsOpen(false);
            }}
          >
            <motion.section
              className="settings-modal"
              role="dialog"
              aria-modal="true"
              aria-labelledby="settings-title"
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 18, scale: 0.98 }}
            >
              <div className="modal-header">
                <div>
                  <span className="section-kicker">Device preferences</span>
                  <h2 id="settings-title">Workspace settings</h2>
                </div>
                <button
                  type="button"
                  className="icon-button"
                  onClick={() => setSettingsOpen(false)}
                  aria-label="Close settings"
                >
                  <X size={18} />
                </button>
              </div>
              <label className="settings-row">
                <span>
                  <strong>Compact graph labels</strong>
                  <small>Reduce labels until a node is selected.</small>
                </span>
                <input type="checkbox" defaultChecked />
              </label>
              <label className="settings-row">
                <span>
                  <strong>Camera overlays</strong>
                  <small>Show observed tracks on recorded footage.</small>
                </span>
                <input type="checkbox" defaultChecked />
              </label>
              <label className="settings-row">
                <span>
                  <strong>Reduce motion</strong>
                  <small>Also follows your operating system preference.</small>
                </span>
                <input type="checkbox" />
              </label>
              <button
                className="primary-button modal-action"
                type="button"
                onClick={() => setSettingsOpen(false)}
              >
                Save on this device
              </button>
            </motion.section>
          </motion.div>
        )}
      </AnimatePresence>
    </MotionConfig>
  );
}
