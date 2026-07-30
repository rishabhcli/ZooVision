"use client";

import {
  Bell,
  Camera,
  Check,
  Contrast,
  LayoutDashboard,
  MonitorCog,
  Moon,
  ShieldCheck,
} from "lucide-react";
import { useState } from "react";

type ToggleRowProps = {
  title: string;
  description: string;
  defaultChecked?: boolean;
};

function ToggleRow({
  title,
  description,
  defaultChecked = false,
}: ToggleRowProps) {
  return (
    <label className="settings-toggle-row">
      <span>
        <strong>{title}</strong>
        <small>{description}</small>
      </span>
      <input type="checkbox" defaultChecked={defaultChecked} />
    </label>
  );
}

export function SettingsWorkspace() {
  const [density, setDensity] = useState<"comfortable" | "compact">(
    "comfortable",
  );
  const [saved, setSaved] = useState(false);

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
          onClick={() => {
            setSaved(true);
            window.setTimeout(() => setSaved(false), 2200);
          }}
        >
          <Check size={15} />
          Save changes
        </button>
      </header>

      <div className="settings-content-grid">
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
                  className={density === option ? "active" : undefined}
                  aria-pressed={density === option}
                  onClick={() => setDensity(option)}
                  key={option}
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
          <ToggleRow
            title="Compact graph labels"
            description="Show full graph labels only when a node is selected."
            defaultChecked
          />
          <ToggleRow
            title="Preserve open assistant"
            description="Keep the evidence assistant expanded when changing pages."
            defaultChecked
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
            title="Track overlays"
            description="Display source-provided track boxes over recorded footage."
            defaultChecked
          />
          <ToggleRow
            title="Timeline thumbnails"
            description="Show source-aligned preview frames in the editor timeline."
            defaultChecked
          />
          <ToggleRow
            title="Identity confidence"
            description="Show confidence values alongside selected tracks."
            defaultChecked
          />
        </section>

        <section className="settings-section">
          <div className="settings-section-heading">
            <span>
              <Bell size={17} />
            </span>
            <div>
              <h2>Review notifications</h2>
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
            title="Morning briefing ready"
            description="Notify this device when the overnight briefing is prepared."
            defaultChecked
          />
          <ToggleRow
            title="Data-gap review"
            description="Surface missing camera coverage as a review item."
            defaultChecked
          />
        </section>

        <section className="settings-section">
          <div className="settings-section-heading">
            <span>
              <MonitorCog size={17} />
            </span>
            <div>
              <h2>Accessibility</h2>
              <p>Adjust motion and contrast for this device.</p>
            </div>
          </div>
          <ToggleRow
            title="Reduce motion"
            description="Reduce carousel, drawer, and timeline spring animations."
          />
          <ToggleRow
            title="Increase contrast"
            description="Strengthen borders and secondary text contrast."
          />
          <div className="settings-device-row">
            <Contrast size={16} />
            <span>
              <strong>Theme</strong>
              <small>
                <Moon size={12} /> Night workspace · black and blue
              </small>
            </span>
          </div>
        </section>
      </div>

      {saved && (
        <div className="settings-save-toast" role="status">
          <Check size={15} />
          Preferences saved on this device.
        </div>
      )}
    </div>
  );
}
