import type { Metadata } from "next";
import { LandingExperience } from "./landing-experience";

export const metadata: Metadata = {
  title: "Night Watch",
  description:
    "Try ZooVision's evidence-led overnight animal welfare workflow.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function LandingPage() {
  return <LandingExperience />;
}
