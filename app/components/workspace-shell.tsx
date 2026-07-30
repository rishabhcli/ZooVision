"use client";

import { AnimatePresence, MotionConfig, motion } from "motion/react";
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
  ScanLine,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import {
  FormEvent,
  ReactNode,
  useEffect,
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
  body: string;
  citations?: string[];
};

const routeOptions = [
  { label: "Monitor", href: "/monitor", icon: Monitor },
  { label: "Node graph", href: "/graph", icon: Network },
  { label: "Analysis", href: "/analysis", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

const initialChats: Record<string, ChatMessage[]> = {
  "/monitor": [
    {
      id: "monitor-user",
      role: "user",
      body: "What is happening in the selected segment?",
    },
    {
      id: "monitor-assistant",
      role: "assistant",
      body: "Track 14 shows continuous pacing from 02:00–02:14. Identity confidence is 0.86, so verify the clip before recording an outcome.",
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
      body: "The graph connects a 14-minute pacing observation to the deterministic pacing > 10 min rule and its source clip.",
      citations: ["EVT-1842", "Rule 10.1"],
    },
  ],
  "/analysis": [
    {
      id: "analysis-user",
      role: "user",
      body: "Summarize the enclosure tonight.",
    },
    {
      id: "analysis-assistant",
      role: "assistant",
      body: "Coverage is complete. Rex has one acknowledged review item; Zuri has no notable events in the monitored window.",
      citations: ["Overnight review", "Coverage"],
    },
  ],
  "/settings": [
    {
      id: "settings-user",
      role: "user",
      body: "What do these preferences affect?",
    },
    {
      id: "settings-assistant",
      role: "assistant",
      body: "These controls change the frontend on this device. They do not change deterministic rules, severity, or paging policy.",
      citations: ["Device preferences"],
    },
  ],
};

export function WorkspaceShell({
  children,
  title,
  eyebrow,
}: WorkspaceShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const profileRef = useRef<HTMLDivElement>(null);
  const [chatCollapsed, setChatCollapsed] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [messagesByRoute, setMessagesByRoute] = useState<
    Record<string, ChatMessage[]>
  >({});
  const [draft, setDraft] = useState("");

  useEffect(() => {
    function closeProfile(event: MouseEvent) {
      if (!profileRef.current?.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    }
    document.addEventListener("mousedown", closeProfile);
    return () => document.removeEventListener("mousedown", closeProfile);
  }, []);

  const messages =
    messagesByRoute[pathname] ??
    initialChats[pathname] ??
    initialChats["/monitor"];

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value) return;

    const timestamp = Date.now();
    setMessagesByRoute((current) => ({
      ...current,
      [pathname]: [
        ...(current[pathname] ??
          initialChats[pathname] ??
          initialChats["/monitor"]),
        { id: `user-${timestamp}`, role: "user", body: value },
        {
          id: `assistant-${timestamp}`,
          role: "assistant",
          body: "This frontend prototype is using the evidence visible on this page. Connect the read-only evidence service when the backend is ready.",
          citations: ["Frontend prototype"],
        },
      ],
    }));
    setDraft("");
  }

  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ type: "spring", visualDuration: 0.32, bounce: 0.05 }}
    >
      <main className="app-frame">
        <motion.aside
          className="chat-rail"
          animate={{ width: chatCollapsed ? 64 : 326 }}
          data-collapsed={chatCollapsed}
          aria-label="ZooVision Assistant"
        >
          <div className="chat-rail-header">
            <span className="assistant-mark" aria-hidden="true">
              <Sparkles size={16} />
            </span>
            <AnimatePresence initial={false}>
              {!chatCollapsed && (
                <motion.div
                  className="chat-heading"
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -8 }}
                >
                  <strong>ZooVision Assistant</strong>
                  <span>Evidence on this page</span>
                </motion.div>
              )}
            </AnimatePresence>
            <button
              type="button"
              className="icon-button chat-toggle"
              onClick={() => setChatCollapsed((current) => !current)}
              aria-label={
                chatCollapsed ? "Expand assistant" : "Collapse assistant"
              }
              aria-expanded={!chatCollapsed}
            >
              {chatCollapsed ? (
                <ChevronRight size={17} />
              ) : (
                <ChevronLeft size={17} />
              )}
            </button>
          </div>

          {chatCollapsed ? (
            <button
              type="button"
              className="collapsed-chat-content"
              onClick={() => setChatCollapsed(false)}
              aria-label="Expand assistant"
            >
              <MessageSquareText size={18} />
              <span>AI</span>
            </button>
          ) : (
            <motion.div
              className="chat-body"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
            >
              <div className="chat-context">
                <span className="status-dot" />
                <span>{eyebrow}</span>
              </div>
              <div className="message-list" aria-live="polite">
                {messages.map((message) => (
                  <article
                    className={`chat-message ${message.role}`}
                    key={message.id}
                  >
                    <span className="message-avatar" aria-hidden="true">
                      {message.role === "assistant" ? (
                        <Bot size={14} />
                      ) : (
                        <CircleUserRound size={14} />
                      )}
                    </span>
                    <div>
                      <div className="message-meta">
                        <strong>
                          {message.role === "assistant" ? "ZooVision" : "You"}
                        </strong>
                        <span>05:41</span>
                      </div>
                      <p className="message-copy">{message.body}</p>
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
                  placeholder="Ask about this page…"
                  aria-label="Ask ZooVision Assistant"
                  rows={2}
                />
                <div className="composer-actions">
                  <button
                    type="button"
                    className="icon-button"
                    aria-label="Attach evidence"
                  >
                    <Paperclip size={16} />
                  </button>
                  <button
                    type="submit"
                    className="send-button"
                    aria-label="Send message"
                    disabled={!draft.trim()}
                  >
                    <Send size={15} />
                  </button>
                </div>
              </form>
              <p className="chat-disclaimer">
                Verify source evidence before recording an outcome.
              </p>
            </motion.div>
          )}
        </motion.aside>

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
                          router.push("/settings");
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
    </MotionConfig>
  );
}
