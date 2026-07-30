"use client";

import { AnimatePresence, MotionConfig, motion } from "motion/react";
import {
  BarChart3,
  Bell,
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
  Play,
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
import { api, type ChatMoment } from "../lib/api";

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
  moments?: ChatMoment[];
  time?: string;
};

const routeOptions = [
  { label: "Monitor", href: "/monitor", icon: Monitor },
  { label: "Node graph", href: "/graph", icon: Network },
  { label: "Analysis", href: "/analysis", icon: BarChart3 },
];

const initialChats: Record<string, ChatMessage[]> = {
  "/monitor": [
    {
      id: "monitor-intro",
      role: "assistant",
      body: "Ask what happened or describe a moment to find. I can open the matching footage.",
      citations: ["TwelveLabs moments", "Connected shift record"],
    },
  ],
  "/graph": [
    {
      id: "graph-intro",
      role: "assistant",
      body: "Ask about nodes in the live Neo4j video context graph.",
      citations: ["Neo4j graph"],
    },
  ],
  "/analysis": [
    {
      id: "analysis-intro",
      role: "assistant",
      body: "Ask for a factual summary of events, rules, reviews, or data gaps.",
      citations: ["Backend evidence"],
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
  const isEvidenceLayout =
    pathname === "/monitor" || pathname === "/graph" || pathname === "/analysis";
  const profileRef = useRef<HTMLDivElement>(null);
  const [chatCollapsed, setChatCollapsed] = useState(pathname === "/monitor");
  const [profileOpen, setProfileOpen] = useState(false);
  const [messagesByRoute, setMessagesByRoute] = useState<
    Record<string, ChatMessage[]>
  >({});
  const [draft, setDraft] = useState("");
  const [chatPending, setChatPending] = useState(false);

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

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value || chatPending) return;

    const timestamp = Date.now();
    const currentMessages =
      messagesByRoute[pathname] ??
      initialChats[pathname] ??
      initialChats["/monitor"];
    setMessagesByRoute((current) => ({
      ...current,
      [pathname]: [
        ...currentMessages,
        { id: `user-${timestamp}`, role: "user", body: value },
      ],
    }));
    setDraft("");
    setChatPending(true);
    try {
      const history = currentMessages
        .filter((message) => !message.id.endsWith("-intro"))
        .map((message) => ({ role: message.role, content: message.body }))
        .slice(-11);
      const reply = await api.chat([
        ...history,
        { role: "user" as const, content: value },
      ]);
      setMessagesByRoute((current) => ({
        ...current,
        [pathname]: [
          ...(current[pathname] ?? currentMessages),
          {
            id: `assistant-${timestamp}`,
            role: "assistant",
            body: reply.answer,
            citations: reply.cited_ids,
            moments: reply.moments,
          },
        ],
      }));
    } catch (caught) {
      setMessagesByRoute((current) => ({
        ...current,
        [pathname]: [
          ...(current[pathname] ?? currentMessages),
          {
            id: `assistant-error-${timestamp}`,
            role: "assistant",
            body:
              caught instanceof Error
                ? caught.message
                : "The evidence service is unavailable.",
          },
        ],
      }));
    } finally {
      setChatPending(false);
    }
  }

  return (
    <MotionConfig
      reducedMotion="user"
      transition={{ type: "spring", visualDuration: 0.32, bounce: 0.05 }}
    >
      <main
        className={`app-frame ${isEvidenceLayout ? "evidence-layout" : ""}`}
      >
        <motion.aside
          className="chat-rail"
          animate={{ width: chatCollapsed ? 56 : isEvidenceLayout ? 220 : 326 }}
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
                  <strong>
                    {isEvidenceLayout ? "AI Assistant" : "ZooVision Assistant"}
                  </strong>
                  {!isEvidenceLayout && <span>Evidence on this page</span>}
                </motion.div>
              )}
            </AnimatePresence>
            <button
              type="button"
              className="icon-button chat-toggle"
              data-testid="chat-toggle"
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
                {!isEvidenceLayout && <span className="status-dot" />}
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
                          {isEvidenceLayout && message.role === "assistant"
                            ? "Evidence"
                            : message.role === "assistant"
                              ? "ZooVision"
                              : "You"}
                        </strong>
                        <span>{message.time ?? "05:41"}</span>
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
                      {message.moments && message.moments.length > 0 && (
                        <div className="chat-moment-row">
                          {message.moments.map((moment) => (
                            <button
                              type="button"
                              key={moment.observation_id}
                              data-testid="chat-moment"
                              title={`Open ${moment.camera_id} at ${moment.start_seconds.toFixed(1)} seconds`}
                              onClick={() => {
                                const detail = {
                                  sourcePath: moment.source_path,
                                  seconds: moment.start_seconds,
                                };
                                sessionStorage.setItem(
                                  "zoovision:pending-moment",
                                  JSON.stringify(detail),
                                );
                                if (pathname !== "/monitor") {
                                  router.push("/monitor");
                                  return;
                                }
                                window.dispatchEvent(
                                  new CustomEvent("zoovision:seek-moment", {
                                    detail,
                                  }),
                                );
                              }}
                            >
                              <Play size={12} fill="currentColor" />
                              <span>{moment.label}</span>
                              <small>{moment.camera_id}</small>
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
                    disabled={!draft.trim() || chatPending}
                  >
                    <Send size={15} />
                  </button>
                </div>
              </form>
              <p className="chat-disclaimer">
                AI responses may be inaccurate. Verify all results.
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
                  {/* The public asset works in local, Worker, and static preview runtimes. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    className="brand-mark-image"
                    src="/brand/zoovision-icon.png"
                    alt=""
                    width={30}
                    height={30}
                  />
                </span>
                <span>ZooVision</span>
              </button>
              <span className="topbar-divider" />
              {isEvidenceLayout ? (
                <strong className="evidence-workspace-title">
                  Overnight evidence workspace
                </strong>
              ) : (
                <div className="page-context">
                  <span>{eyebrow}</span>
                  <strong>{title}</strong>
                </div>
              )}
            </div>

            <nav className="route-tabs" aria-label="Workspace pages">
              {routeOptions
                .filter(
                  (option) => !isEvidenceLayout || option.href !== "/settings",
                )
                .map((option) => {
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
                    {!isEvidenceLayout && <Icon size={15} />}
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
              {isEvidenceLayout ? (
                <>
                  <button
                    type="button"
                    className="evidence-header-icon"
                    aria-label="Switch appearance"
                  >
                    <Moon size={17} />
                  </button>
                  <button
                    type="button"
                    className="evidence-header-icon"
                    aria-label="Notifications"
                  >
                    <Bell size={17} />
                  </button>
                </>
              ) : (
                <>
                  <div className="shadow-badge">
                    <ShieldCheck size={14} />
                    Shadow mode
                  </div>
                  <div className="shift-status">
                    <Moon size={15} />
                    <span>Night shift</span>
                    <strong>05:42</strong>
                  </div>
                </>
              )}
              <div className="profile-menu" ref={profileRef}>
                <button
                  type="button"
                  className="profile-trigger"
                  onClick={() => setProfileOpen((current) => !current)}
                  aria-expanded={profileOpen}
                  aria-haspopup="menu"
                >
                  <span className="profile-avatar">
                    {isEvidenceLayout ? (
                      <CircleUserRound size={17} />
                    ) : (
                      "MC"
                    )}
                  </span>
                  {!isEvidenceLayout && (
                    <>
                      <span className="profile-copy">
                        <strong>Maria Chen</strong>
                        <small>Night keeper</small>
                      </span>
                      <ChevronDown size={15} />
                    </>
                  )}
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
                        <span>Settings</span>
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
