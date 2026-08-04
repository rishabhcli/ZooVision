import type { Metadata } from "next";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export const metadata: Metadata = {
  title: "Terms",
};

export default function TermsPage() {
  return (
    <main className="legal-page">
      <nav className="legal-nav" aria-label="Legal navigation">
        <Link href="/"><ArrowLeft size={15} /> Back to ZooVision</Link>
        <span className="legal-kicker">Product boundary</span>
      </nav>
      <header className="legal-hero">
        <span className="legal-kicker">Terms · draft for review</span>
        <h1>Support welfare work. Keep authority human.</h1>
        <p>
          ZooVision is an operational welfare-support tool for observing recorded
          evidence, preserving context, and routing constrained keeper checks. It
          is not a medical device, an autonomous enclosure controller, or a
          replacement for trained staff judgment.
        </p>
      </header>
      <div className="legal-content">
        <div className="legal-sections">
          <section>
            <h2>Permitted use</h2>
            <p>
              Use the workspace with footage and care records that the operating
              organization is authorized to process. Keep staff identities,
              contact details, and animal records limited to the people and systems
              that need them.
            </p>
          </section>
          <section>
            <h2>Human review is required</h2>
            <p>
              A routed event is evidence for a welfare check, not a diagnosis or a
              treatment instruction. Staff must review the source clip, account for
              uncertainty, and record the outcome before taking operational action.
            </p>
          </section>
          <section>
            <h2>Provider and integration status</h2>
            <p>
              Provider models, quotas, timestamps, pricing, and connection health
              can change. A readiness badge, fixture mode, or local adapter is not
              proof of a production integration. Operators must verify the active
              environment before relying on delivery or graph writes.
            </p>
          </section>
          <section>
            <h2>Production access</h2>
            <p>
              Production operator actions require the deployment&apos;s trusted
              access layer to authenticate the staff member. Names entered by a
              browser are not an identity proof and are ignored for production
              audit fields.
            </p>
          </section>
          <section>
            <h2>Availability and change</h2>
            <p>
              The local build may be incomplete or run in shadow mode. Features,
              retention settings, and integrations require deployment-specific
              validation. These draft terms should be replaced by the operating
              organization&apos;s approved service terms before public launch.
            </p>
          </section>
        </div>
        <aside className="legal-aside">
          <strong>Authority boundary</strong>
          <p>
            ZooVision can observe, log, retrieve, notify, and record outcomes. It
            does not diagnose, medicate, dispense treatment, or actuate an enclosure.
          </p>
        </aside>
      </div>
    </main>
  );
}
