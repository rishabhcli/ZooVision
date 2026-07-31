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
  Play,
  Send,
  Settings,
  ShieldCheck,
  Sparkles,
  X,
} from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import {
  FormEvent,
  KeyboardEvent as ReactKeyboardEvent,
  ReactNode,
  useEffect,
  useRef,
  useState,
} from "react";
import { api, type ChatMoment } from "../lib/api";
import {
  applyWorkspacePreferences,
  DEFAULT_WORKSPACE_PREFERENCES,
  listenForWorkspacePreferences,
  readWorkspacePreferences,
  type WorkspacePreferences,
} from "../lib/workspace-preferences";

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

type AssistantContext = {
  animalId: string | null;
  animalName: string | null;
  enclosureId: string | null;
  cameraId: string | null;
  sourcePath: string | null;
};

const emptyAssistantContext: AssistantContext = {
  animalId: null,
  animalName: null,
  enclosureId: null,
  cameraId: null,
  sourcePath: null,
};

const ASSISTANT_STATE_KEY = "zoovision:assistant-expanded";

function citationLabel(citation: string, index: number) {
  if (
    /^(?:(animal|alert|chk|chunk|event|evt|gap|obs|observation)[_-][a-z0-9_-]+|[a-f0-9]{24,}|[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12})$/i.test(citation)
  ) {
    return `Verified evidence ${index + 1}`;
  }
  return citation;
}

const routeOptions = [
  { label: "Monitor", href: "/monitor", icon: Monitor },
  { label: "Node graph", href: "/graph", icon: Network },
  { label: "Analysis", href: "/analysis", icon: BarChart3 },
  { label: "Settings", href: "/settings", icon: Settings },
];

const onboardingSteps = [
  {
    title: "Node graph",
    description:
      "Trace how animals, cameras, observations, welfare events, and keeper outcomes connect.",
    icon: Network,
  },
  {
    title: "Analysis",
    description:
      "Review the whole shift in plain language, including rules, coverage, and review status.",
    icon: BarChart3,
  },
  {
    title: "AI chatbot",
    description:
      "Ask about the selected animal or camera, then open the cited footage at the matching moment.",
    icon: Bot,
  },
] as const;

const initialChats: Record<string, ChatMessage[]> = {
  "/monitor": [
    {
      id: "monitor-intro",
      role: "assistant",
      body: "Select a camera, then ask about the animal's recorded activity or a welfare event.",
    },
  ],
  "/graph": [
    {
      id: "graph-intro",
      role: "assistant",
      body: "Ask about nodes in the live Neo4j video context graph.",
    },
  ],
  "/analysis": [
    {
      id: "analysis-intro",
      role: "assistant",
      body: "Ask for a factual summary of events, rules, reviews, or data gaps.",
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
  const isEvidenceLayout = ["/monitor", "/graph", "/analysis", "/settings"].includes(
    pathname,
  );
  const profileRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);
  const tourDialogRef = useRef<HTMLElement>(null);
  const tourReturnFocusRef = useRef<HTMLElement | null>(null);
  const [chatCollapsed, setChatCollapsed] = useState(isEvidenceLayout);
  const [profileOpen, setProfileOpen] = useState(false);
  const [tourStep, setTourStep] = useState<number | null>(null);
  const [messagesByRoute, setMessagesByRoute] = useState<
    Record<string, ChatMessage[]>
  >({});
  const [draft, setDraft] = useState("");
  const [chatPending, setChatPending] = useState(false);
  const [assistantContext, setAssistantContext] = useState<AssistantContext>(
    emptyAssistantContext,
  );
  const [workspacePreferences, setWorkspacePreferences] =
    useState<WorkspacePreferences>(DEFAULT_WORKSPACE_PREFERENCES);

  useEffect(() => {
    const storedPreferences = readWorkspacePreferences(window.localStorage);
    applyWorkspacePreferences(document.documentElement, storedPreferences);
    const wideViewport = !window.matchMedia("(max-width: 1280px)").matches;
    const storedAssistantState = window.sessionStorage.getItem(
      ASSISTANT_STATE_KEY,
    );
    const hydrationFrame = window.requestAnimationFrame(() => {
      setWorkspacePreferences(storedPreferences);
      if (
        storedPreferences.preserveOpenAssistant &&
        wideViewport &&
        storedAssistantState === "true"
      ) {
        setChatCollapsed(false);
      }
    });

    const stopListening = listenForWorkspacePreferences(window, (nextPreferences) => {
      applyWorkspacePreferences(document.documentElement, nextPreferences);
      setWorkspacePreferences(nextPreferences);
      if (!nextPreferences.preserveOpenAssistant) setChatCollapsed(true);
    });
    return () => {
      window.cancelAnimationFrame(hydrationFrame);
      stopListening();
    };
  }, []);

  useEffect(() => {
    if (!workspacePreferences.preserveOpenAssistant) return;
    window.sessionStorage.setItem(
      ASSISTANT_STATE_KEY,
      String(!chatCollapsed),
    );
  }, [chatCollapsed, workspacePreferences.preserveOpenAssistant]);

  useEffect(() => {
    if (!isEvidenceLayout) return;
    const compactViewport = window.matchMedia("(max-width: 1280px)");
    const collapseForCompactViewport = () => {
      if (compactViewport.matches) setChatCollapsed(true);
    };
    collapseForCompactViewport();
    compactViewport.addEventListener("change", collapseForCompactViewport);
    return () =>
      compactViewport.removeEventListener("change", collapseForCompactViewport);
  }, [isEvidenceLayout, pathname]);

  useEffect(() => {
    function closeProfile(event: MouseEvent) {
      if (!profileRef.current?.contains(event.target as Node)) {
        setProfileOpen(false);
      }
    }
    function closeProfileFromKeyboard(event: globalThis.KeyboardEvent) {
      if (event.key !== "Escape") return;
      setProfileOpen(false);
      profileRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    }
    document.addEventListener("mousedown", closeProfile);
    document.addEventListener("keydown", closeProfileFromKeyboard);
    return () => {
      document.removeEventListener("mousedown", closeProfile);
      document.removeEventListener("keydown", closeProfileFromKeyboard);
    };
  }, []);

  useEffect(() => {
    if (pathname !== "/monitor") return;
    const params = new URLSearchParams(window.location.search);
    if (params.get("tour") !== "1") return;
    tourReturnFocusRef.current = document.activeElement as HTMLElement | null;
    setTourStep(0);
  }, [pathname]);

  useEffect(() => {
    if (tourStep === null) return;
    const frame = window.requestAnimationFrame(() => {
      tourDialogRef.current?.focus();
    });
    return () => window.cancelAnimationFrame(frame);
  }, [tourStep]);

  useEffect(() => {
    function updateAssistantContext(event: Event) {
      const detail = (event as CustomEvent<AssistantContext>).detail;
      if (detail) setAssistantContext(detail);
    }

    const stored = sessionStorage.getItem("zoovision:assistant-context");
    if (stored) {
      try {
        setAssistantContext(JSON.parse(stored) as AssistantContext);
      } catch {
        sessionStorage.removeItem("zoovision:assistant-context");
      }
    }
    window.addEventListener(
      "zoovision:assistant-context",
      updateAssistantContext,
    );
    return () =>
      window.removeEventListener(
        "zoovision:assistant-context",
        updateAssistantContext,
      );
  }, []);

  const conversationKey =
    pathname === "/monitor" && assistantContext.sourcePath
      ? `${pathname}:${assistantContext.sourcePath}`
      : pathname;
  const storedMessages =
    messagesByRoute[conversationKey] ??
    initialChats[pathname] ??
    initialChats["/monitor"];
  const messages = storedMessages.map((message) =>
    message.id === "monitor-intro" &&
    assistantContext.animalName &&
    assistantContext.cameraId
      ? {
          ...message,
          body: `Ask about ${assistantContext.animalName}'s recorded activity on ${assistantContext.cameraId}, or ask what triggered a welfare event.`,
        }
      : message,
  );
  const currentTourStep =
    tourStep === null ? null : onboardingSteps[tourStep];
  const TourIcon = currentTourStep?.icon;

  function removeTourQuery() {
    const url = new URL(window.location.href);
    url.searchParams.delete("tour");
    window.history.replaceState(
      window.history.state,
      "",
      `${url.pathname}${url.search}${url.hash}`,
    );
  }

  function dismissTour() {
    removeTourQuery();
    setTourStep(null);
    window.requestAnimationFrame(() => tourReturnFocusRef.current?.focus());
  }

  function completeTour() {
    removeTourQuery();
    setChatCollapsed(false);
    setTourStep(null);
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => composerRef.current?.focus());
    });
  }

  function handleTourKeyDown(event: ReactKeyboardEvent<HTMLElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      dismissTour();
      return;
    }
    if (event.key !== "Tab" || !tourDialogRef.current) return;
    const focusable = Array.from(
      tourDialogRef.current.querySelectorAll<HTMLElement>(
        'button:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
      ),
    );
    if (focusable.length === 0) {
      event.preventDefault();
      return;
    }
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    const active = document.activeElement as HTMLElement | null;
    if (!active || !focusable.includes(active)) {
      event.preventDefault();
      (event.shiftKey ? last : first).focus();
    } else if (event.shiftKey && active === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && active === last) {
      event.preventDefault();
      first.focus();
    }
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const value = draft.trim();
    if (!value || chatPending) return;

    const timestamp = Date.now();
    const currentMessages =
      messagesByRoute[conversationKey] ??
      initialChats[pathname] ??
      initialChats["/monitor"];
    setMessagesByRoute((current) => ({
      ...current,
      [conversationKey]: [
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
      const reply = await api.chat(
        [...history, { role: "user" as const, content: value }],
        assistantContext,
      );
      setMessagesByRoute((current) => ({
        ...current,
        [conversationKey]: [
          ...(current[conversationKey] ?? currentMessages),
          {
            id: `assistant-${timestamp}`,
            role: "assistant",
            body: reply.answer,
            citations:
              reply.citations?.length > 0
                ? reply.citations.map((citation) => citation.label)
                : reply.cited_ids,
            moments: reply.moments,
          },
        ],
      }));
    } catch (caught) {
      setMessagesByRoute((current) => ({
        ...current,
        [conversationKey]: [
          ...(current[conversationKey] ?? currentMessages),
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
      reducedMotion={workspacePreferences.reduceMotion ? "always" : "user"}
      transition={{ type: "spring", visualDuration: 0.32, bounce: 0.05 }}
    >
      <main
        className={`app-frame ${isEvidenceLayout ? "evidence-layout" : ""}`}
        data-route={pathname.replace(/^\//, "") || "home"}
      >
        <AnimatePresence>
          {currentTourStep && TourIcon && tourStep !== null && (
            <motion.div
              className="onboarding-tour-backdrop"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <motion.section
                ref={tourDialogRef}
                className="onboarding-tour-dialog"
                role="dialog"
                aria-modal="true"
                aria-labelledby="onboarding-tour-title"
                aria-describedby="onboarding-tour-description"
                tabIndex={-1}
                onKeyDown={handleTourKeyDown}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 8 }}
              >
                <header className="onboarding-tour-header">
                  <span>ZooVision tour</span>
                  <button
                    type="button"
                    className="onboarding-tour-close"
                    aria-label="Close tour"
                    onClick={dismissTour}
                  >
                    <X size={17} />
                  </button>
                </header>

                <div
                  className="onboarding-tour-progress"
                  role="progressbar"
                  aria-label="Tour progress"
                  aria-valuemin={1}
                  aria-valuemax={onboardingSteps.length}
                  aria-valuenow={tourStep + 1}
                >
                  {onboardingSteps.map((step, index) => (
                    <span
                      key={step.title}
                      data-complete={index <= tourStep}
                      aria-hidden="true"
                    />
                  ))}
                </div>

                <div className="onboarding-tour-content">
                  <span className="onboarding-tour-icon" aria-hidden="true">
                    <TourIcon size={22} />
                  </span>
                  <p className="onboarding-tour-step">
                    Step {tourStep + 1} of {onboardingSteps.length}
                  </p>
                  <h2 id="onboarding-tour-title">{currentTourStep.title}</h2>
                  <p id="onboarding-tour-description">
                    {currentTourStep.description}
                  </p>
                </div>

                <footer className="onboarding-tour-actions">
                  <button
                    type="button"
                    className="onboarding-tour-secondary"
                    disabled={tourStep === 0}
                    onClick={() => setTourStep((step) => Math.max(0, (step ?? 0) - 1))}
                  >
                    <ChevronLeft size={16} />
                    Back
                  </button>
                  {tourStep < onboardingSteps.length - 1 ? (
                    <button
                      type="button"
                      className="onboarding-tour-primary"
                      onClick={() =>
                        setTourStep((step) =>
                          Math.min(onboardingSteps.length - 1, (step ?? 0) + 1),
                        )
                      }
                    >
                      Next
                      <ChevronRight size={16} />
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="onboarding-tour-primary"
                      onClick={completeTour}
                    >
                      Open AI chatbot
                      <MessageSquareText size={16} />
                    </button>
                  )}
                </footer>
              </motion.section>
            </motion.div>
          )}
        </AnimatePresence>

        <motion.aside
          className="chat-rail"
          animate={{ width: chatCollapsed ? 56 : isEvidenceLayout ? 220 : 326 }}
          data-collapsed={chatCollapsed}
          aria-label="ZooVision Assistant"
        >
          <div className="chat-rail-header" hidden={chatCollapsed}>
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
                <span>
                  {pathname === "/monitor" &&
                  assistantContext.animalName &&
                  assistantContext.cameraId
                    ? `${assistantContext.animalName} · ${assistantContext.cameraId}`
                    : eyebrow}
                </span>
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
                      {message.citations && message.citations.length > 0 && (
                        <p
                          className="message-copy"
                          aria-label="Evidence sources"
                        >
                          <strong>Evidence: </strong>
                          {message.citations
                            .map((citation, index) =>
                              citationLabel(citation, index),
                            )
                            .join(" · ")}
                        </p>
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
                  ref={composerRef}
                  value={draft}
                  onChange={(event) => setDraft(event.target.value)}
                  placeholder={
                    pathname === "/monitor" &&
                    assistantContext.animalName &&
                    assistantContext.cameraId
                      ? `Ask about ${assistantContext.animalName} on ${assistantContext.cameraId}…`
                      : "Ask about recorded evidence…"
                  }
                  aria-label="Ask ZooVision Assistant"
                  rows={2}
                />
                <div className="composer-actions">
                  <span aria-hidden="true" />
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
                    <Icon className="route-tab-icon" size={15} aria-hidden="true" />
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
                    aria-label="Open appearance settings"
                    title="Appearance settings"
                    onClick={() => router.push("/settings#accessibility")}
                  >
                    <Moon size={17} />
                  </button>
                  <button
                    type="button"
                    className="evidence-header-icon"
                    aria-label="Open review notification settings"
                    title="Review notifications"
                    onClick={() => router.push("/settings#notifications")}
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
                  className={`profile-trigger ${
                    pathname === "/settings" ? "active" : ""
                  }`}
                  onClick={() => setProfileOpen((current) => !current)}
                  onKeyDown={(event: ReactKeyboardEvent<HTMLButtonElement>) => {
                    if (event.key !== "ArrowDown") return;
                    event.preventDefault();
                    setProfileOpen(true);
                    window.requestAnimationFrame(() => {
                      profileRef.current
                        ?.querySelector<HTMLButtonElement>("[role='menuitem']")
                        ?.focus();
                    });
                  }}
                  aria-expanded={profileOpen}
                  aria-haspopup="menu"
                  aria-controls="profile-menu"
                  aria-label="Open profile and settings menu"
                  aria-current={pathname === "/settings" ? "page" : undefined}
                  title="Profile and settings"
                >
                  <span className="profile-avatar">
                    {pathname === "/settings" ? (
                      <Settings size={17} />
                    ) : isEvidenceLayout ? (
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
                      id="profile-menu"
                      className="dropdown-menu profile-dropdown"
                      role="menu"
                      onKeyDown={(event: ReactKeyboardEvent<HTMLDivElement>) => {
                        const items = Array.from(
                          event.currentTarget.querySelectorAll<HTMLElement>(
                            "[role='menuitem']",
                          ),
                        );
                        if (items.length === 0) return;
                        const currentIndex = items.indexOf(
                          document.activeElement as HTMLElement,
                        );
                        let nextIndex = currentIndex;
                        if (event.key === "ArrowDown") {
                          nextIndex = (currentIndex + 1) % items.length;
                        } else if (event.key === "ArrowUp") {
                          nextIndex =
                            (currentIndex - 1 + items.length) % items.length;
                        } else if (event.key === "Home") {
                          nextIndex = 0;
                        } else if (event.key === "End") {
                          nextIndex = items.length - 1;
                        } else {
                          return;
                        }
                        event.preventDefault();
                        items[nextIndex]?.focus();
                      }}
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
                        aria-current={pathname === "/settings" ? "page" : undefined}
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
