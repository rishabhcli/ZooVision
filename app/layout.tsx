import type { Metadata } from "next";
import { headers } from "next/headers";
import "@fontsource-variable/jetbrains-mono";
import "@fontsource-variable/manrope";
import "./globals.css";
import "./legal-pages.css";
import "./operations.css";

const description =
  "Evidence-led animal welfare monitoring with deterministic triage and human review.";

export async function generateMetadata(): Promise<Metadata> {
  const requestHeaders = await headers();
  const host =
    requestHeaders.get("x-forwarded-host") ?? requestHeaders.get("host");
  const protocol =
    requestHeaders.get("x-forwarded-proto") ??
    (host?.startsWith("localhost") ? "http" : "https");
  const metadataBase = new URL(
    host ? `${protocol}://${host}` : "http://localhost:3000",
  );
  const socialImage = new URL("/og.png", metadataBase).toString();

  return {
    metadataBase,
    title: {
      default: "ZooVision",
      template: "%s · ZooVision",
    },
    description,
    icons: {
      icon: "/favicon.svg",
    },
    openGraph: {
      type: "website",
      title: "ZooVision",
      description,
      siteName: "ZooVision",
      images: [
        {
          url: socialImage,
          width: 1731,
          height: 909,
          alt: "ZooVision evidence-led overnight welfare monitoring workspace",
        },
      ],
    },
    twitter: {
      card: "summary_large_image",
      title: "ZooVision",
      description,
      images: [socialImage],
    },
  };
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
