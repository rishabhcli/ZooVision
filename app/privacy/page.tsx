import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata: Metadata = {
  title: "Privacy",
};

export default function PrivacyPage() {
  return (
    <main className="legal-page">
      <nav className="legal-nav" aria-label="Legal navigation">
        <Link href="/"><ArrowLeft size={15} /> Back to ZooVision</Link>
        <span className="legal-kicker">Data handling</span>
      </nav>
      <header className="legal-hero">
        <span className="legal-kicker">Privacy · draft for review</span>
        <h1>Evidence stays accountable.</h1>
        <p>
          ZooVision handles camera footage, extracted clips, animal care context,
          staff identities, and keeper outcomes as sensitive operational data.
          This page describes the product boundary in the current build.
        </p>
      </header>
      <div className="legal-content">
        <div className="legal-sections">
          <section>
            <h2>What the workspace records</h2>
            <p>
              The application can store uploaded video metadata, timestamped
              observations, deterministic triage results, alert acknowledgement,
              and human outcomes. Provider credentials and raw secrets stay in
              environment configuration and are not part of ordinary event text.
            </p>
          </section>
          <section>
            <h2>Retention is configuration</h2>
            <p>
              Raw chunks, analysis artifacts, and alert clips have separate
              retention settings. The documented development defaults are 7 days
              for raw chunks, 30 days for analysis JSON, and 90 days for alert
              clips. Operators should confirm the active deployment configuration
              before using production footage.
            </p>
          </section>
          <section>
            <h2>Access and review</h2>
            <p>
              A welfare event keeps its source evidence, rule identifier, stable
              event identifier, and acknowledgement state. The product is designed
              for authorized staff workflows. Production deployments require an
              external access layer to authenticate staff and forward an operator
              identity; authentication, tenancy, and public deployment controls
              must still be verified for the operating organization.
            </p>
          </section>
          <section>
            <h2>Questions and corrections</h2>
            <p>
              For a real deployment, the operating organization should publish a
              named privacy contact and its applicable retention, access, and
              incident-response procedures. This local build does not claim those
              procedures are configured.
            </p>
          </section>
        </div>
        <aside className="legal-aside">
          <strong>No invented evidence</strong>
          <p>
            Missing footage is recorded as uncertainty or a data gap. It is never
            silently converted into a normal result.
          </p>
        </aside>
      </div>
    </main>
  );
}
