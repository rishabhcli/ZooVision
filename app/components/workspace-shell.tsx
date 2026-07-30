"use client";

import {
  AnimatePresence,
  MotionConfig,
  motion,
  useReducedMotion,
} from "motion/react";
import {
  BarChart3,
  Bot,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleUserRound,
  MessageSquareText,
  Monitor,
  Moon,
  Network,
  Paperclip,
  PawPrint,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import {
  FormEvent,
  ReactNode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

type WorkspaceShellProps = {
  children: ReactNode;
  title: string;
  eyebrow: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  body: ReactNode;
  citations?: string[];
};

const routeOptions = [
  { label: "Monitor", href: "/monitor", icon: Monitor },
  { label: "Node graph", href: "/graph", icon: Network },
  { label: "Analysis", href: "/analysis", icon: BarChart3 },
];

const initialChats: Record<string, ChatMessage[]> = {
  "/monitor": [
    {
      id: "monitor-user",
      role: "user",
      body: "Is the selected track Rex or Zuri?",
    },
    {
      id: "monitor-assistant",
      role: "assistant",
      body: (
        <>
          The selected track is linked to Rex in this segment. Identity
          confidence is 0.86, so verify it against the clip before recording an
          outcome.
        </>
      ),
      citations: ["Track 14", "Clip 02:06"],
    },
  ],
  "/graph": [
    {
      id: "graph-user",
      role: "user",
      body: "What changed for Rex tonight?",
    },
    {
      id: "graph-assistant",
      role: "assistant",
      body: (
        <>
          Rex paced for 14 minutes from 02:00–02:14, 3.1σ above his daytime
          baseline. Severity came from the deterministic rule{" "}
          <strong>pacing &gt; 10 min</strong>.
        </>
      ),
      citations: ["Event EVT-1842", "Baseline"],
    },
  ],
  "/analysis": [
    {
      id: "analysis-user",
      role: "user",
      body: "Summarize tonight for this enclosure.",
    },
    {
      id: "analysis-assistant",
      role: "assistant",
      body: (
        <ul className="assistant-summary">
          <li>Rex: pacing 02:00–02:14</li>
          <li>Zuri: no notable events</li>
          <li>Coverage: complete</li>
        </ul>
      ),
      citations: ["Event EVT-1842", "Camera coverage"],
    },
  ],
};

function routeLabel(pathname: string) {
  return (
    routeOptions.find((option) => option.href === pathname)?.label ?? "Monitor"
  );
}

export function WorkspaceShell({
  children,
  title,
  eyebrow,
}: WorkspaceShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const menuRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [messagesByRoute, setMessagesByRoute] = useState<
    Record<string, ChatMessage[]>
  >({});
  const [draft, setDraft] = useState("");

  useEffect(() => {
    function closeMenus(event: MouseEvent) {
      const target = event.target as Node;
      if (!menuRef.current?.contains(target)) setNavOpen(false);
      if (!profileRef.current?.contains(target)) setProfileOpen(false);
    }
    document.addEventListener("mousedown", closeMenus);
    return () => document.removeEventListener("mousedown", closeMenus);
  }, []);

  const activeLabel = useMemo(() => routeLabel(pathname), [pathname]);
  const messages =
    messagesByRoute[pathname] ??
    initialChats[pathname] ??
    initialChats["/monitor"];

  function toggleChat() {
    setChatCollapsed((current) => {
      const next = !current;
      window.localStorage.setItem(
        "zoovision-chat-collapsed",
        String(next),
      );
      return next;
    });
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;

    setMessagesByRoute((current) => {
      const routeMessages =
        current[pathname] ??
        initialChats[pathname] ??
        initialChats["/monitor"];
      const timestamp = Date.now();

      return {
        ...current,
        [pathname]: [
          ...routeMessages,
          {
            id: `user-${timestamp}`,
            role: "user",
            body: value,
          },
          {
            id: `assistant-${timestamp}`,
            role: "assistant",
            body: (
              <>
                This frontend prototype is using the selected page&apos;s
                evidence context. Connect the chat to the read-only evidence
                service when the backend is ready.
              </>
            ),
            citations: ["Frontend prototype"],
          },
        ],
      };
    });
    setDraft("");
  }

  return (
    <MotionConfig
      reducedMotion="user"
      transition={{
        type: "spring",
        visualDuration: reduceMotion ? 0 : 0.32,
        bounce: 0.08,
      }}
    >
      <main className="app-frame">
        <motion.aside
          className="chat-rail"
          animate={{ width: chatCollapsed ? 72 : 348 }}
          aria-label="ZooVision Assistant"
          data-collapsed={chatCollapsed}
        >
          <div className="chat-rail-header">
            <div className="assistant-mark" aria-hidden="true">
              <Sparkles size={17} />
            </div>
            <AnimatePresence initial={false}>
              {!chatCollapsed && (
                <motion.div
                  className="chat-heading"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                >
                  <strong>ZooVision Assistant</strong>
                  <span>Evidence-only workspace chat</span>
                </motion.div>
              )}
            </AnimatePresence>
            <button
              className="icon-button chat-toggle"
              type="button"
              onClick={toggleChat}
              aria-label={
                chatCollapsed ? "Expand assistant" : "Collapse assistant"
              }
              aria-expanded={!chatCollapsed}
            >
              {chatCollapsed ? (
                <ChevronRight size={18} />
              ) : (
                <ChevronLeft size={18} />
              )}
            </button>
          </div>

          {chatCollapsed ? (
            <div className="collapsed-chat-content" aria-hidden="true">
              <MessageSquareText size={19} />
              <span>AI</span>
              <div className="collapsed-chat-line" />
            </div>
          ) : (
            <motion.div
              className="chat-body"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="chat-context">
                <span className="status-dot" />
                {eyebrow}
              </div>
              <div className="message-list" aria-live="polite">
                {messages.map((message) => (
                  <article
                    className={`chat-message ${message.role}`}
                    key={message.id}
                  >
                    <div className="message-avatar" aria-hidden="true">
                      {message.role === "assistant" ? (
                        <Bot size={15} />
                      ) : (
                        <CircleUserRound size={15} />
                      )}
                    </div>
                    <div>
                      <div className="message-meta">
                        <strong>
                          {message.role === "assistant"
                            ? "ZooVision"
                            : "You"}
                        </strong>
                        <span>05:41</span>
                      </div>
                      <div className="message-copy">{message.body}</div>
                      {message.citations && (
                        <div className="citation-row">
                          {message.citations.map((citation) => (
                            <button type="button" key={citation}>
                              {citation}
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  </article>
                ))}
              </div>
              <form className="chat-composer" onSubmit={handleSubmit}>
                <textarea
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={`Ask about this ${activeLabel.toLowerCase()}…`}
                  aria-label="Ask ZooVision Assistant"
                  rows={2}
                />
                <div className="composer-actions">
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Attach evidence"
                  >
                    <Paperclip size={17} />
                  </button>
                  <button
                    type="submit"
                    className="send-button"
                    aria-label="Send message"
                    disabled={!draft.trim()}
                  >
                    <Send size={16} />
                  </button>
                </div>
              </form>
              <p className="chat-disclaimer">
                Assistant responses can be incomplete. Verify source evidence.
              </p>
            </motion.div>
          )}
        </motion.aside>

        <motion.section className="workspace" layout>
          <header className="topbar">
            <div className="topbar-left">
              <button
                type="button"
                className="brand"
                onClick={() => router.push("/monitor")}
                aria-label="ZooVision monitor"
              >
                <span className="brand-mark" aria-hidden="true">
                  <PawPrint size={19} />
                </span>
                <span>ZooVision</span>
              </button>
              <span className="topbar-divider" />
              <div className="workspace-menu" ref={menuRef}>
                <button
                  type="button"
                  className="workspace-menu-trigger"
                  onClick={() => setNavOpen((current) => !current)}
                  aria-expanded={navOpen}
                  aria-haspopup="menu"
                >
                  <span>{activeLabel}</span>
                  <ChevronDown size={15} />
                </button>
                <AnimatePresence>
                  {navOpen && (
                    <motion.div
                      className="dropdown-menu workspace-dropdown"
                      role="menu"
                      initial={{ opacity: 0, y: -6, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: -6, scale: 0.98 }}
                    >
                      <span className="menu-label">Workspace</span>
                      {routeOptions.map((option) => {
                        const Icon = option.icon;
                        const isActive = pathname === option.href;
                        return (
                          <button
                            key={option.href}
                            type="button"
                            role="menuitem"
                            className={isActive ? "active" : undefined}
                            onClick={() => {
                              setNavOpen(false);
                              router.push(option.href);
                            }}
                          >
                            <Icon size={16} />
                            <span>{option.label}</span>
                            {isActive && <span className="menu-check">•</span>}
                          </button>
                        );
                      })}
                      <div className="menu-separator" />
                      <button
                        type="button"
                        role="menuitem"
                        onClick={() => {
                          setNavOpen(false);
                          setSettingsOpen(true);
                        }}
                      >
                        <Settings size={16} />
                        <span>Settings</span>
                      </button>
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
              <div className="page-context">
                <span>{eyebrow}</span>
                <strong>{title}</strong>
              </div>
            </div>

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
                        <span className="profile-avatar large">MC</span>
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
        </motion.section>
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
