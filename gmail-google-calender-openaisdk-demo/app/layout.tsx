import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Gmail + Calendar agent",
  description: "An OpenAI agent for Gmail and Google Calendar, executed through Swytchcode.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
