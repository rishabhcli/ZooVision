"use client";

import {
  Bell,
  Camera,
  Check,
  Contrast,
  Database,
  LayoutDashboard,
  MonitorCog,
  Moon,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, type ReadinessPayload } from "../lib/api";
import {
  applyWorkspacePreferences,
  DEFAULT_WORKSPACE_PREFERENCES,
  dispatchWorkspacePreferences,
  listenForWorkspacePreferences,
  persistWorkspacePreferences,
  readWorkspacePreferences,
  type WorkspacePreferences,
} from "../lib/workspace-preferences";

type BooleanPreference = {
  [Key in keyof WorkspacePreferences]: WorkspacePreferences[Key] extends boolean
    ? Key
    : never;
}[keyof WorkspacePreferences];

type ToggleRowProps = {
  preference: BooleanPreference;
  title: string;
  description: string;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
};

function ToggleRow({
  preference,
  title,
  description,
  checked,
  onCheckedChange,
}: ToggleRowProps) {
  return (
    <label className="settings-toggle-row">
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <input
        type="checkbox"
        name={preference}
        checked={checked}
        onChange={(event) => onCheckedChange(event.target.checked)}
      />
    </label>
  );
}

type ProviderVisualStatus = "healthy" | "unverified" | "unavailable";

const providerLabels: Record<string, string> = {
  agentcore: "AgentCore",
  aws_storage: "AWS storage",
  bedrock_marengo: "Bedrock Marengo",
  eventbridge_scheduler: "EventBridge Scheduler",
  neo4j: "Neo4j",
  openai: "OpenAI",
  slack: "Slack",
  twelve_labs: "TwelveLabs",
  twelvelabs: "TwelveLabs",
  yolo: "YOLO",
};

function providerLabel(provider: string) {
  return (
    providerLabels[provider.toLowerCase()] ??
    provider
      .split("_")
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

function providerStatus(status: string): {
  dataStatus: ProviderVisualStatus;
  label: string;
} {
  if (status === "healthy") {
    return { dataStatus: "healthy", label: "Healthy" };
  }
  if (status === "enabled_unverified") {
    return { dataStatus: "unverified", label: "Enabled, not yet verified" };
  }
  if (status === "configured_disabled") {
    return { dataStatus: "unavailable", label: "Configured, disabled" };
  }
  if (status === "not_configured") {
    return { dataStatus: "unavailable", label: "Not configured" };
  }
  return { dataStatus: "unavailable", label: "Unavailable" };
}

export function SettingsWorkspace() {
  const [preferences, setPreferences] = useState<WorkspacePreferences>(
    DEFAULT_WORKSPACE_PREFERENCES,
  );
  const [saveStatus, setSaveStatus] = useState<"idle" | "saved" | "error">(
    "idle",
  );
  const [readiness, setReadiness] = useState<ReadinessPayload | null>(null);
  const saveStatusTimer = useRef<number | null>(null);

  useEffect(() => {
    api.readiness().then(setReadiness).catch(() => setReadiness(null));
  }, []);

  useEffect(() => {
    const storedPreferences = readWorkspacePreferences(window.localStorage);
    applyWorkspacePreferences(document.documentElement, storedPreferences);
    const hydrationFrame = window.requestAnimationFrame(() => {
      setPreferences(storedPreferences);
    });

    const stopListening = listenForWorkspacePreferences(window, (next) => {
      setPreferences(next);
      applyWorkspacePreferences(document.documentElement, next);
    });

    return () => {
      window.cancelAnimationFrame(hydrationFrame);
      stopListening();
      if (saveStatusTimer.current !== null) {
        window.clearTimeout(saveStatusTimer.current);
      }
    };
  }, []);

  function updatePreference<Key extends keyof WorkspacePreferences>(
    key: Key,
    value: WorkspacePreferences[Key],
  ) {
    setPreferences((current) => ({ ...current, [key]: value }));
    setSaveStatus("idle");
  }

  function savePreferences() {
    if (saveStatusTimer.current !== null) {
      window.clearTimeout(saveStatusTimer.current);
    }

    try {
      persistWorkspacePreferences(window.localStorage, preferences);
      applyWorkspacePreferences(document.documentElement, preferences);
      dispatchWorkspacePreferences(window, preferences);
      setSaveStatus("saved");
    } catch {
      setSaveStatus("error");
    }

    saveStatusTimer.current = window.setTimeout(
      () => setSaveStatus("idle"),
      2200,
    );
  }

  return (
    <div className="page-stack settings-page">
      <header className="settings-page-heading">
        <div>
          <span className="section-kicker">Workspace preferences</span>
          <h1>Settings</h1>
          <p>
            Configure this device’s display, recorded footage, and review
            behavior.
          </p>
        </div>
        <button
          type="button"
          className="primary-button"
          onClick={savePreferences}
        >
          <Check size={15} />
          Save changes
        </button>
      </header>

      <div className="settings-content-grid">
        <section className="settings-section">
          <div className="settings-section-heading">
            <span>
              <Database size={17} />
            </span>
            <div>
              <h2>Backend connections</h2>
              <p>Live readiness reported by the ZooVision API.</p>
            </div>
          </div>
          {readiness ? (
            Object.entries(readiness.providers).map(([provider, state]) => {
              const status = providerStatus(state.status);
              return (
                <div className="settings-device-row" key={provider}>
                  <span
                    className="status-dot"
                    data-status={status.dataStatus}
                    aria-hidden="true"
                  />
                  <span>
                    <strong>{providerLabel(provider)}</strong>
                    <small>
                      {status.label}
                      {provider.toLowerCase() === "neo4j" && state.read_connected
                        ? " · Live read connection"
                        : ""}
                    </small>
                  </span>
                </div>
              );
            })
          ) : (
            <div className="settings-policy-note">
              <ShieldCheck size={16} />
              <p>Backend readiness is unavailable.</p>
            </div>
          )}
        </section>

        <section className="settings-section">
          <div className="settings-section-heading">
            <span>
              <LayoutDashboard size={17} />
            </span>
            <div>
              <h2>Workspace display</h2>
              <p>Control density and information shown across the dashboard.</p>
            </div>
          </div>
          <div className="settings-field">
            <span>
              <strong>Interface density</strong>
              <small>Choose the spacing used by cards, tables, and controls.</small>
            </span>
            <div className="density-control" role="group" aria-label="Interface density">
              {(["comfortable", "compact"] as const).map((option) => (
                <button
                  type="button"
                  className={preferences.density === option ? "active" : undefined}
                  aria-pressed={preferences.density === option}
                  onClick={() => updatePreference("density", option)}
                  key={option}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
          <ToggleRow
            preference="compactGraphLabels"
            title="Compact graph labels"
            description="Show full graph labels only when a node is selected."
            checked={preferences.compactGraphLabels}
            onCheckedChange={(checked) =>
              updatePreference("compactGraphLabels", checked)
            }
          />
          <ToggleRow
            preference="preserveOpenAssistant"
            title="Preserve open assistant"
            description="Keep the evidence assistant expanded between pages on wide screens."
            checked={preferences.preserveOpenAssistant}
            onCheckedChange={(checked) =>
              updatePreference("preserveOpenAssistant", checked)
            }
          />
        </section>

        <section className="settings-section">
          <div className="settings-section-heading">
            <span>
              <Camera size={17} />
            </span>
            <div>
              <h2>Camera review</h2>
              <p>Configure recorded footage and analysis overlays.</p>
            </div>
          </div>
          <ToggleRow
            preference="trackOverlays"
            title="Track overlays"
            description="Display source-provided track boxes over recorded footage."
            checked={preferences.trackOverlays}
            onCheckedChange={(checked) =>
              updatePreference("trackOverlays", checked)
            }
          />
          <ToggleRow
            preference="timelineThumbnails"
            title="Source previews"
            description="Show recorded frame previews in the camera source gallery."
            checked={preferences.timelineThumbnails}
            onCheckedChange={(checked) =>
              updatePreference("timelineThumbnails", checked)
            }
          />
          <ToggleRow
            preference="identityConfidence"
            title="Identity confidence"
            description="Show confidence values alongside selected tracks."
            checked={preferences.identityConfidence}
            onCheckedChange={(checked) =>
              updatePreference("identityConfidence", checked)
            }
          />
        </section>

        <section
          className="settings-section"
          id="notifications"
          aria-labelledby="notifications-title"
        >
          <div className="settings-section-heading">
            <span>
              <Bell size={17} />
            </span>
            <div>
              <h2 id="notifications-title">Review notifications</h2>
              <p>Notification controls remain constrained by welfare policy.</p>
            </div>
          </div>
          <div className="settings-policy-note">
            <ShieldCheck size={16} />
            <p>
              Shadow mode remains enabled. Only deterministic night-shift rules
              can create review items.
            </p>
          </div>
          <ToggleRow
            preference="morningBriefingReady"
            title="Briefing control"
            description="Show the morning briefing control on the Analysis page."
            checked={preferences.morningBriefingReady}
            onCheckedChange={(checked) =>
              updatePreference("morningBriefingReady", checked)
            }
          />
          <ToggleRow
            preference="dataGapReview"
            title="Data-gap review"
            description="Show missing camera coverage in this device’s review queue."
            checked={preferences.dataGapReview}
            onCheckedChange={(checked) =>
              updatePreference("dataGapReview", checked)
            }
          />
        </section>

        <section
          className="settings-section"
          id="accessibility"
          aria-labelledby="accessibility-title"
        >
          <div className="settings-section-heading">
            <span>
              <MonitorCog size={17} />
            </span>
            <div>
              <h2 id="accessibility-title">Accessibility</h2>
              <p>Adjust motion and contrast for this device.</p>
            </div>
          </div>
          <ToggleRow
            preference="reduceMotion"
            title="Reduce motion"
            description="Reduce carousel, drawer, and timeline spring animations."
            checked={preferences.reduceMotion}
            onCheckedChange={(checked) =>
              updatePreference("reduceMotion", checked)
            }
          />
          <ToggleRow
            preference="increaseContrast"
            title="Increase contrast"
            description="Strengthen borders and secondary text contrast."
            checked={preferences.increaseContrast}
            onCheckedChange={(checked) =>
              updatePreference("increaseContrast", checked)
            }
          />
          <div className="settings-device-row">
            <Contrast size={16} />
            <span>
              <strong>Theme</strong>
              <small>
                <Moon size={12} /> Night workspace · graphite, lime, and teal
              </small>
            </span>
          </div>
        </section>
      </div>

      {saveStatus === "saved" && (
        <div className="settings-save-toast" role="status">
          <Check size={15} />
          Preferences saved on this device.
        </div>
      )}
      {saveStatus === "error" && (
        <div className="settings-save-toast" role="alert">
          Preferences could not be saved on this device.
        </div>
      )}
    </div>
  );
}
