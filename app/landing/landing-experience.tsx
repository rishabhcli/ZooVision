"use client";

/* eslint-disable @next/next/no-img-element */

import {
  ArrowDown,
  ArrowRight,
  BarChart3,
  BellRing,
  Binoculars,
  Bot,
  Check,
  CircleCheck,
  ClipboardCheck,
  Eye,
  Footprints,
  MousePointerClick,
  Moon,
  Network,
  Pause,
  Play,
  QrCode,
  ScanLine,
  ShieldCheck,
  Sun,
  Video,
  Waves,
} from "lucide-react";
import "@fontsource/black-ops-one/400.css";
import "@fontsource/yellowtail/400.css";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { CSSProperties, useEffect, useMemo, useRef, useState } from "react";
import "./landing.css";

type Shift = "night" | "day";
type ScanState = "idle" | "scanning" | "complete";

type Scenario = {
  id: string;
  tab: string;
  animal: string;
  species: string;
  camera: string;
  timestamp: string;
  poster: string;
  behavior: string;
  duration: string;
  context: string;
  severity: "HIGH" | "LOW" | "NONE";
  rule: string;
  action: string;
  actionLabel: string;
  marker: number;
  box: CSSProperties;
  note: string;
};

const scenarios: Scenario[] = [
  {
    id: "pacing",
    tab: "Repeated path",
    animal: "Amara",
    species: "African lion",
    camera: "CAM-07A",
    timestamp: "02:14:32",
    poster: "/camera-posters/cam-07a-lion.jpg",
    behavior: "Repeated pacing path",
    duration: "21m 08s",
    context: "No water contact · 6h 24m",
    severity: "HIGH",
    rule: "R004_PACING_20M_NO_WATER_6H",
    action: "welfare_check",
    actionLabel: "Route welfare check",
    marker: 68,
    box: { left: "43%", top: "28%", width: "34%", height: "48%" },
    note: "Policy matched two measured thresholds. A keeper still decides what happens next.",
  },
  {
    id: "water",
    tab: "Water station",
    animal: "Sabi",
    species: "African elephant",
    camera: "CAM-05N",
    timestamp: "03:41:06",
    poster: "/camera-posters/cam-05n-elephant.jpg",
    behavior: "Water bowl tipped",
    duration: "00m 42s",
    context: "Object state changed in zone W-2",
    severity: "LOW",
    rule: "R008_WATER_BOWL_TIPPED",
    action: "verify_water",
    actionLabel: "Route water check",
    marker: 42,
    box: { left: "58%", top: "47%", width: "26%", height: "28%" },
    note: "The observation supports a practical check, not a diagnosis or treatment.",
  },
  {
    id: "quiet",
    tab: "Quiet interval",
    animal: "Kito",
    species: "Mountain gorilla",
    camera: "CAM-03Y",
    timestamp: "04:26:51",
    poster: "/camera-posters/cam-03y-gorilla.jpg",
    behavior: "Resting in usual zone",
    duration: "18m 12s",
    context: "Within daytime-derived baseline",
    severity: "NONE",
    rule: "NO_RULE_FIRED",
    action: "observe",
    actionLabel: "Save observation",
    marker: 24,
    box: { left: "24%", top: "24%", width: "29%", height: "53%" },
    note: "No notable rule matched. ZooVision records normal nights and data gaps too.",
  },
];

const noxTips = [
  "Start in the monitor, then follow any observation into its connected evidence.",
  "Night events never rewrite the baseline they are measured against.",
  "If the camera goes dark, I log a data gap. I do not fill in the blanks.",
];

const explorationSteps = [
  {
    label: "Node graph",
    title: "Follow every connection",
    description:
      "Trace animals, cameras, observations, clips, events, and keeper outcomes through the connected evidence graph.",
    href: "/graph",
    action: "Explore the graph",
    icon: Network,
  },
  {
    label: "Analysis",
    title: "Read the whole shift",
    description:
      "Compare behavior, rule events, coverage, and review status in a plain-language operational summary.",
    href: "/analysis",
    action: "Open analysis",
    icon: BarChart3,
  },
  {
    label: "AI chatbot",
    title: "Ask the evidence",
    description:
      "Ask what an animal was doing and jump back to the cited moment without losing the selected camera context.",
    href: "/monitor",
    action: "Ask a question",
    icon: Bot,
  },
] as const;

function scrollToExplore() {
  document
    .getElementById("explore")
    ?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function LandingExperience() {
  const reduceMotion = useReducedMotion();
  const scanTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [scenarioId, setScenarioId] = useState(scenarios[0].id);
  const [shift, setShift] = useState<Shift>("night");
  const [scanState, setScanState] = useState<ScanState>("idle");
  const [playback, setPlayback] = useState(false);
  const [reviewed, setReviewed] = useState(false);
  const [timeline, setTimeline] = useState(scenarios[0].marker);
  const [tipIndex, setTipIndex] = useState(0);
  const [pointer, setPointer] = useState({ x: 0, y: 0 });

  const scenario = useMemo(
    () =>
      scenarios.find((item) => item.id === scenarioId) ?? scenarios[0],
    [scenarioId],
  );

  useEffect(() => {
    return () => {
      if (scanTimer.current) clearTimeout(scanTimer.current);
    };
  }, []);

  useEffect(() => {
    if (!playback) return;
    const interval = window.setInterval(() => {
      setTimeline((value) => (value >= 100 ? 0 : value + 0.4));
    }, 80);
    return () => window.clearInterval(interval);
  }, [playback]);

  function selectScenario(nextScenario: Scenario) {
    if (scanTimer.current) clearTimeout(scanTimer.current);
    setScenarioId(nextScenario.id);
    setTimeline(nextScenario.marker);
    setScanState("idle");
    setPlayback(false);
    setReviewed(false);
  }

  function runScan() {
    if (scanTimer.current) clearTimeout(scanTimer.current);
    setReviewed(false);
    setScanState("scanning");
    setPlayback(true);
    scanTimer.current = setTimeout(() => {
      setTimeline(scenario.marker);
      setPlayback(false);
      setScanState("complete");
    }, reduceMotion ? 250 : 1450);
  }

  const isDay = shift === "day";
  const canPage = !isDay && scenario.severity !== "NONE";

  return (
    <main
      className="landing"
      onPointerMove={(event) => {
        if (reduceMotion) return;
        const x = event.clientX / window.innerWidth - 0.5;
        const y = event.clientY / window.innerHeight - 0.5;
        setPointer({ x, y });
      }}
      style={
        {
          "--pointer-x": pointer.x,
          "--pointer-y": pointer.y,
        } as CSSProperties
      }
    >
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="hero-image" aria-hidden="true" />
        <div className="hero-grid" aria-hidden="true" />
        <div className="hero-scan" aria-hidden="true" />

        <nav className="landing-nav" aria-label="Landing page">
          <Link
            className="landing-brand"
            href="/"
            aria-label="ZooVision home"
          >
            <span className="landing-brand-mark">
              <Eye size={18} strokeWidth={2.2} />
            </span>
            <span
              className="brand-wordmark brand-wordmark-nav"
              aria-hidden="true"
            >
              <span className="brand-zoo">ZOO</span>
              <span className="brand-vision">VISION</span>
            </span>
          </Link>
          <div className="landing-nav-actions">
            <span className="preview-flag">
              INTERACTIVE EVIDENCE DEMO
            </span>
            <a
              className="nav-try"
              href="/monitor?tour=1"
            >
              Try Out
              <ArrowRight size={15} />
            </a>
          </div>
        </nav>

        <motion.div
          className="hero-copy"
          initial={reduceMotion ? false : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.75, ease: [0.2, 0.8, 0.2, 1] }}
        >
          <div className="hero-kicker">
            <span className="live-pip" />
            Overnight welfare support
          </div>
          <h1 id="landing-title" aria-label="ZooVision">
            <span
              className="brand-wordmark brand-wordmark-hero"
              aria-hidden="true"
            >
              <span className="brand-zoo">ZOO</span>
              <span className="brand-vision">VISION</span>
            </span>
          </h1>
          <p>
            See the night.
            <br />
            Keep the decision human.
          </p>
          <div className="hero-actions">
            <motion.a
              className="try-out-cta"
              href="/monitor?tour=1"
              whileHover={reduceMotion ? undefined : { y: -4, x: -2 }}
              whileTap={reduceMotion ? undefined : { scale: 0.98 }}
            >
              <span className="try-out-mark" aria-hidden="true">
                <Eye size={21} strokeWidth={2.4} />
              </span>
              <span>
                <small>OPEN THE INTERACTIVE DEMO</small>
                <strong>Try Out</strong>
              </span>
              <ArrowRight size={22} />
            </motion.a>
            <span className="hero-proof">
              <ShieldCheck size={17} />
              Evidence, rules, keeper review
            </span>
          </div>
        </motion.div>

        <div className="hero-camera-hud" aria-hidden="true">
          <span>CAM-07A</span>
          <span>02:14:32</span>
          <span className="hud-recording">DEMO</span>
        </div>

        <motion.div
          className="nox-stage"
          initial={reduceMotion ? false : { opacity: 0, x: 30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.3, duration: 0.65 }}
          whileHover={reduceMotion ? undefined : { y: -5 }}
        >
          <button
            className="nox-bubble"
            type="button"
            aria-label="Hear another tip from Nox"
            key={tipIndex}
            onClick={() =>
              setTipIndex((index) => (index + 1) % noxTips.length)
            }
          >
            <span className="nox-name">NOX · NIGHT RANGER</span>
            {noxTips[tipIndex]}
            <span className="nox-next">TAP FOR FIELD NOTE {tipIndex + 1}/3</span>
          </button>
          <span className="nox-ground-shadow" aria-hidden="true" />
          <span className="nox-character">
            <span className="nox-headlamp-signal" aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <img
              src="/landing/nox.png"
              alt="Nox, ZooVision's pixel-art pangolin night ranger"
              width={1254}
              height={1254}
              className="nox-image"
            />
          </span>
        </motion.div>

        <button
          type="button"
          className="hero-scroll"
          onClick={scrollToExplore}
          aria-label="Explore ZooVision"
        >
          <span>EXPLORE THE WORKSPACE</span>
          <ArrowDown size={16} />
        </button>
      </section>

      <section
        className="explore-band"
        id="explore"
        aria-labelledby="explore-title"
      >
        <header className="explore-heading">
          <span className="section-index">01 · START HERE</span>
          <h2 id="explore-title">Three ways to explore one evidence record.</h2>
          <p>
            Begin with the connected story, read the shift-level picture, then
            ask a focused question. Every path leads back to source footage.
          </p>
        </header>

        <ol className="explore-steps">
          {explorationSteps.map((step, index) => {
            const Icon = step.icon;
            return (
              <motion.li
                key={step.label}
                initial={reduceMotion ? false : { opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, amount: 0.25 }}
                transition={{ delay: index * 0.09, duration: 0.45 }}
              >
                <a href={step.href}>
                  <span className="explore-number">0{index + 1}</span>
                  <span className="explore-icon">
                    <Icon size={22} strokeWidth={1.8} />
                  </span>
                  <span className="explore-copy">
                    <small>{step.label}</small>
                    <strong>{step.title}</strong>
                    <p>{step.description}</p>
                  </span>
                  <span className="explore-action">
                    {step.action}
                    <ArrowRight size={16} />
                  </span>
                </a>
              </motion.li>
            );
          })}
        </ol>
      </section>

      <section className="night-lab" id="night-lab" aria-labelledby="lab-title">
        <header className="lab-heading">
          <div>
            <span className="section-index">02 · FIELD TEST</span>
            <h2 id="lab-title">Run one minute of night watch.</h2>
          </div>
          <p>
            Pick a moment, scan the evidence, then decide how it should be
            routed. Follow each observation through baseline context, the first
            matching rule, and a human decision.
          </p>
        </header>

        <div className="scenario-tabs" role="tablist" aria-label="Night moments">
          {scenarios.map((item, index) => (
            <button
              key={item.id}
              id={`scenario-tab-${item.id}`}
              className={item.id === scenario.id ? "active" : ""}
              type="button"
              role="tab"
              aria-selected={item.id === scenario.id}
              aria-controls="night-scenario-panel"
              tabIndex={item.id === scenario.id ? 0 : -1}
              onClick={() => selectScenario(item)}
              onKeyDown={(event) => {
                let nextIndex: number | null = null;

                if (event.key === "ArrowLeft") {
                  nextIndex = (index - 1 + scenarios.length) % scenarios.length;
                } else if (event.key === "ArrowRight") {
                  nextIndex = (index + 1) % scenarios.length;
                } else if (event.key === "Home") {
                  nextIndex = 0;
                } else if (event.key === "End") {
                  nextIndex = scenarios.length - 1;
                }

                if (nextIndex === null) return;

                event.preventDefault();
                const nextScenario = scenarios[nextIndex];
                selectScenario(nextScenario);
                document
                  .getElementById(`scenario-tab-${nextScenario.id}`)
                  ?.focus();
              }}
            >
              <span>0{index + 1}</span>
              <strong>{item.tab}</strong>
              <small>{item.animal}</small>
            </button>
          ))}
        </div>

        <div
          className="simulator-layout"
          id="night-scenario-panel"
          role="tabpanel"
          aria-labelledby={`scenario-tab-${scenario.id}`}
          tabIndex={0}
        >
          <div className="camera-tool">
            <div className="camera-toolbar">
              <div>
                <Video size={15} />
                <strong>{scenario.camera}</strong>
                <span>EVIDENCE DEMO</span>
              </div>
              <div
                className="shift-control"
                role="group"
                aria-label="Shift routing"
              >
                <button
                  type="button"
                  className={shift === "night" ? "active" : ""}
                  onClick={() => {
                    setShift("night");
                    setReviewed(false);
                  }}
                  aria-pressed={shift === "night"}
                >
                  <Moon size={13} />
                  Night
                </button>
                <button
                  type="button"
                  className={shift === "day" ? "active" : ""}
                  onClick={() => {
                    setShift("day");
                    setReviewed(false);
                  }}
                  aria-pressed={shift === "day"}
                >
                  <Sun size={13} />
                  Day
                </button>
              </div>
            </div>

            <div className="camera-frame">
              <AnimatePresence mode="wait">
                <motion.div
                  key={scenario.id}
                  className="camera-scene"
                  initial={reduceMotion ? false : { opacity: 0.2, scale: 1.03 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.4 }}
                >
                  <img
                    src={scenario.poster}
                    alt={`${scenario.species} evidence scene`}
                  />
                </motion.div>
              </AnimatePresence>
              <div className="camera-noise" aria-hidden="true" />
              <div className="camera-corners" aria-hidden="true" />
              <AnimatePresence>
                {scanState !== "idle" && (
                  <motion.div
                    className={`subject-box severity-${scenario.severity.toLowerCase()}`}
                    style={scenario.box}
                    initial={{ opacity: 0, scale: 0.88 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0 }}
                  >
                    <span>
                      {scanState === "scanning"
                        ? "TRACKING"
                        : `${scenario.behavior.toUpperCase()} · ${scenario.severity}`}
                    </span>
                  </motion.div>
                )}
              </AnimatePresence>
              {scanState === "scanning" && (
                <motion.div
                  className="active-scan-line"
                  aria-hidden="true"
                  initial={{ top: "5%" }}
                  animate={{ top: "92%" }}
                  transition={{
                    duration: 1.2,
                    ease: "linear",
                    repeat: reduceMotion ? 0 : 1,
                  }}
                />
              )}
              <div className="camera-stamp">
                <span>{shift.toUpperCase()} SHIFT</span>
                <strong>{scenario.timestamp}</strong>
              </div>
              <button
                className="play-control"
                type="button"
                aria-label={
                  playback ? "Pause evidence" : "Play evidence"
                }
                onClick={() => setPlayback((value) => !value)}
              >
                {playback ? (
                  <Pause size={17} fill="currentColor" />
                ) : (
                  <Play size={17} fill="currentColor" />
                )}
              </button>
            </div>

            <div className="timeline">
              <div className="timeline-labels">
                <span>00:00</span>
                <strong>ACTIVITY TRACE</strong>
                <span>30:00</span>
              </div>
              <div className="timeline-track">
                <div
                  className="timeline-progress"
                  style={{ width: `${timeline}%` }}
                />
                <span
                  className="event-marker"
                  style={{ left: `${scenario.marker}%` }}
                  title="Selected evidence moment"
                />
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={timeline}
                  aria-label="Evidence timeline"
                  onChange={(event) => setTimeline(Number(event.target.value))}
                />
              </div>
              <div className="motion-bars" aria-hidden="true">
                {Array.from({ length: 34 }, (_, index) => (
                  <span
                    key={index}
                    style={{
                      height: `${18 + ((index * 17 + scenario.marker) % 63)}%`,
                    }}
                    className={
                      Math.abs(index / 34 - scenario.marker / 100) < 0.09
                        ? "hot"
                        : ""
                    }
                  />
                ))}
              </div>
            </div>
          </div>

          <aside className="evidence-console" aria-live="polite">
            <div className="console-heading">
              <div>
                <span>DETERMINISTIC REVIEW</span>
                <strong>
                  {scenario.animal} · {scenario.species}
                </strong>
              </div>
              <span
                className={`console-severity severity-${scenario.severity.toLowerCase()}`}
              >
                {scanState === "complete" ? scenario.severity : "READY"}
              </span>
            </div>

            {scanState === "idle" && (
              <div className="console-empty">
                <span className="scan-reticle">
                  <ScanLine size={25} />
                </span>
                <strong>Moment queued</strong>
                <p>
                  Run the scan to trace observation, baseline context, and the
                  first matching rule.
                </p>
                <button type="button" onClick={runScan}>
                  <Binoculars size={16} />
                  Scan this moment
                </button>
              </div>
            )}

            {scanState === "scanning" && (
              <div className="console-scanning">
                <span className="pixel-loader" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                  <i />
                  <i />
                </span>
                <strong>Following the evidence...</strong>
                <p>Schema check · baseline lookup · first-match policy</p>
              </div>
            )}

            {scanState === "complete" && (
              <motion.div
                className="evidence-result"
                initial={reduceMotion ? false : { opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <ol className="evidence-steps">
                  <li>
                    <span>
                      <Eye size={14} />
                    </span>
                    <div>
                      <small>OBSERVATION</small>
                      <strong>{scenario.behavior}</strong>
                      <p>{scenario.duration}</p>
                    </div>
                    <Check size={15} />
                  </li>
                  <li>
                    <span>
                      <Waves size={14} />
                    </span>
                    <div>
                      <small>BASELINE CONTEXT</small>
                      <strong>{scenario.context}</strong>
                      <p>Prior daytime shifts only</p>
                    </div>
                    <Check size={15} />
                  </li>
                  <li>
                    <span>
                      <Footprints size={14} />
                    </span>
                    <div>
                      <small>RULE FIRED</small>
                      <strong>{scenario.rule}</strong>
                      <p>First match wins · Python policy</p>
                    </div>
                    <Check size={15} />
                  </li>
                </ol>

                <div className="route-result">
                  <span>{isDay ? "DAY ROUTE" : "NIGHT ROUTE"}</span>
                  <strong>
                    {isDay
                      ? "Baseline context only"
                      : scenario.severity === "NONE"
                        ? "Record without alert"
                        : scenario.action}
                  </strong>
                  <p>
                    {isDay
                      ? "Day observations refine context. They never page staff."
                      : scenario.note}
                  </p>
                </div>

                <button
                  className={`review-action ${reviewed ? "reviewed" : ""}`}
                  type="button"
                  onClick={() => setReviewed((value) => !value)}
                >
                  {reviewed ? (
                    <CircleCheck size={18} />
                  ) : canPage ? (
                    <BellRing size={18} />
                  ) : (
                    <ClipboardCheck size={18} />
                  )}
                  <span>
                    {reviewed
                      ? "Human decision recorded"
                      : isDay
                        ? "Save to daytime baseline"
                        : scenario.actionLabel}
                  </span>
                  {!reviewed && <ArrowRight size={16} />}
                </button>

                <button className="scan-again" type="button" onClick={runScan}>
                  Replay evidence trace
                </button>
              </motion.div>
            )}
          </aside>
        </div>
      </section>

      <section className="guardrail-band" aria-labelledby="guardrail-title">
        <div className="guardrail-intro">
          <span className="section-index">03 · THE PROMISE</span>
          <h2 id="guardrail-title">Watchful and human-led.</h2>
          <p>
            ZooVision observes, preserves evidence, and routes factual checks
            while keeper judgment remains final.
          </p>
        </div>
        <div className="guardrail-list">
          <div>
            <span>01</span>
            <Eye size={20} />
            <strong>Observe</strong>
            <p>Timestamped behavior with the source clip attached.</p>
          </div>
          <div>
            <span>02</span>
            <ScanLine size={20} />
            <strong>Apply policy</strong>
            <p>Explicit Python rules assign severity and preserve rule_fired.</p>
          </div>
          <div>
            <span>03</span>
            <ShieldCheck size={20} />
            <strong>Keeper review</strong>
            <p>Every routed check ends with a clear human decision.</p>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <div className="footer-mascot">
          <img
            src="/landing/nox.png"
            alt=""
            width={1254}
            height={1254}
          />
        </div>
        <div className="footer-copy">
          <span>NIGHT WATCH IS READY</span>
          <h2>Every alert should earn attention.</h2>
          <p>
            Explore the interactive keeper demo here, or scan the field pass to
            open its evidence workspace on another device.
          </p>
          <a className="footer-enter" href="/monitor?tour=1">
            Try Out
            <ArrowRight size={17} />
          </a>
        </div>
        <div className="qr-pass footer-qr-pass">
          <a
            href="https://zoovision.tech/monitor"
            target="_blank"
            rel="noreferrer"
            aria-label="Click or scan to open the ZooVision monitor"
          >
            <span className="qr-pass-head">
              <span>
                <QrCode size={14} />
                NOX&apos;S NIGHT PASS
              </span>
              <small>LINK · 07</small>
            </span>
            <span className="qr-frame">
              <img
                src="/landing/monitor-qr.png"
                alt="QR code opening the ZooVision monitor"
                width={492}
                height={492}
              />
            </span>
            <span className="qr-caption">
              <strong>CLICK OR SCAN</strong>
              <small>ZOOVISION.TECH/MONITOR</small>
            </span>
            <span className="qr-action">
              <MousePointerClick size={16} />
              Open monitor demo
              <ArrowRight size={15} />
            </span>
          </a>
          <span className="qr-pixels" aria-hidden="true">
            <i />
            <i />
            <i />
            <i />
          </span>
        </div>
        <p className="footer-legal">
          ZooVision is an evidence-led welfare-support tool with keeper judgment
          at the center.
        </p>
      </footer>
    </main>
  );
}
