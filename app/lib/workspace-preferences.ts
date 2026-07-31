export type WorkspaceDensity = "comfortable" | "compact";

export type WorkspacePreferences = {
  density: WorkspaceDensity;
  compactGraphLabels: boolean;
  preserveOpenAssistant: boolean;
  trackOverlays: boolean;
  timelineThumbnails: boolean;
  identityConfidence: boolean;
  morningBriefingReady: boolean;
  dataGapReview: boolean;
  reduceMotion: boolean;
  increaseContrast: boolean;
};

export const WORKSPACE_PREFERENCES_STORAGE_KEY =
  "zoovision:workspace-preferences";
export const WORKSPACE_PREFERENCES_EVENT =
  "zoovision:workspace-preferences";

export const DEFAULT_WORKSPACE_PREFERENCES: WorkspacePreferences = {
  density: "comfortable",
  compactGraphLabels: true,
  preserveOpenAssistant: true,
  trackOverlays: true,
  timelineThumbnails: true,
  identityConfidence: true,
  morningBriefingReady: true,
  dataGapReview: true,
  reduceMotion: false,
  increaseContrast: false,
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function normalizeWorkspacePreferences(
  value: unknown,
): WorkspacePreferences {
  if (!isRecord(value)) return { ...DEFAULT_WORKSPACE_PREFERENCES };

  const normalized = { ...DEFAULT_WORKSPACE_PREFERENCES };
  const density = value.density;
  if (density === "comfortable" || density === "compact") {
    normalized.density = density;
  }

  for (const key of [
    "compactGraphLabels",
    "preserveOpenAssistant",
    "trackOverlays",
    "timelineThumbnails",
    "identityConfidence",
    "morningBriefingReady",
    "dataGapReview",
    "reduceMotion",
    "increaseContrast",
  ] as const) {
    if (typeof value[key] === "boolean") normalized[key] = value[key];
  }

  return normalized;
}

export function readWorkspacePreferences(
  storage: Pick<Storage, "getItem">,
): WorkspacePreferences {
  try {
    const stored = storage.getItem(WORKSPACE_PREFERENCES_STORAGE_KEY);
    return stored
      ? normalizeWorkspacePreferences(JSON.parse(stored) as unknown)
      : { ...DEFAULT_WORKSPACE_PREFERENCES };
  } catch {
    return { ...DEFAULT_WORKSPACE_PREFERENCES };
  }
}

export function persistWorkspacePreferences(
  storage: Pick<Storage, "setItem">,
  preferences: WorkspacePreferences,
) {
  storage.setItem(
    WORKSPACE_PREFERENCES_STORAGE_KEY,
    JSON.stringify(normalizeWorkspacePreferences(preferences)),
  );
}

export function applyWorkspacePreferences(
  documentRoot: HTMLElement,
  preferences: WorkspacePreferences,
) {
  const normalized = normalizeWorkspacePreferences(preferences);
  documentRoot.setAttribute("data-density", normalized.density);
  documentRoot.setAttribute(
    "data-reduced-motion",
    String(normalized.reduceMotion),
  );
  documentRoot.setAttribute(
    "data-increased-contrast",
    String(normalized.increaseContrast),
  );
  documentRoot.setAttribute(
    "data-compact-graph-labels",
    String(normalized.compactGraphLabels),
  );
  documentRoot.setAttribute(
    "data-preserve-open-assistant",
    String(normalized.preserveOpenAssistant),
  );
  documentRoot.setAttribute(
    "data-track-overlays",
    String(normalized.trackOverlays),
  );
  documentRoot.setAttribute(
    "data-timeline-thumbnails",
    String(normalized.timelineThumbnails),
  );
  documentRoot.setAttribute(
    "data-identity-confidence",
    String(normalized.identityConfidence),
  );
  documentRoot.setAttribute(
    "data-morning-briefing-ready",
    String(normalized.morningBriefingReady),
  );
  documentRoot.setAttribute(
    "data-data-gap-review",
    String(normalized.dataGapReview),
  );
}

export function dispatchWorkspacePreferences(
  target: Window,
  preferences: WorkspacePreferences,
) {
  target.dispatchEvent(
    new CustomEvent<WorkspacePreferences>(WORKSPACE_PREFERENCES_EVENT, {
      detail: normalizeWorkspacePreferences(preferences),
    }),
  );
}

export function listenForWorkspacePreferences(
  target: Window,
  listener: (preferences: WorkspacePreferences) => void,
) {
  const handlePreferences = (event: Event) => {
    const customEvent = event as CustomEvent<unknown>;
    listener(normalizeWorkspacePreferences(customEvent.detail));
  };

  target.addEventListener(WORKSPACE_PREFERENCES_EVENT, handlePreferences);
  return () =>
    target.removeEventListener(WORKSPACE_PREFERENCES_EVENT, handlePreferences);
}
