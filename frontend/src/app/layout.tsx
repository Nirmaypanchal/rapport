import type { Metadata, Viewport } from "next";
import { Bricolage_Grotesque, IBM_Plex_Mono, Schibsted_Grotesk } from "next/font/google";
import "./globals.css";
import { Shell } from "@/components/shell";
import { Toaster } from "@/components/ui/sonner";
import { ConfirmProvider } from "@/components/confirm";

const ui = Schibsted_Grotesk({ variable: "--font-ui", subsets: ["latin"], weight: ["400", "500", "600", "700"], display: "swap" });
const display = Bricolage_Grotesque({ variable: "--font-display", subsets: ["latin"], weight: ["500", "600", "700"], display: "swap" });
const mono = IBM_Plex_Mono({ variable: "--font-mono", subsets: ["latin"], weight: ["400", "500", "600"], display: "swap" });

export const metadata: Metadata = {
  title: "Rapport",
  description: "Every voice recording in one place: transcribed, speaker-tagged and summarized on this Mac.",
  icons: { icon: "data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><circle cx='50' cy='50' r='40' fill='%23F2541B'/></svg>" },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f2f2ef" },
    { media: "(prefers-color-scheme: dark)", color: "#121210" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${ui.variable} ${display.variable} ${mono.variable} h-full`}>
      <body className="h-full">
        <ConfirmProvider>
          <Shell>{children}</Shell>
        </ConfirmProvider>
        <Toaster position="bottom-center" />
      </body>
    </html>
  );
}
