import type { Metadata } from "next";
import { LandingExperience } from "./landing/landing-experience";

export const metadata: Metadata = {
  title: "Overnight welfare monitoring",
  description:
    "Explore ZooVision's evidence graph, shift analysis, and evidence-grounded AI assistant.",
};

export default function Home() {
  return <LandingExperience />;
}
