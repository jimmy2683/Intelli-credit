import "./globals.css";
import type { Metadata } from "next";
import React from "react";
import Header from "@/components/Header";
import ThemeScript from "@/components/ThemeScript";

export const metadata: Metadata = {
  title: "Credit Intel — AI-Powered Credit Appraisal",
  description: "Corporate credit appraisal workbench with explainable AI scoring, evidence traceability, and CAM generation.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body>
        <div className="shell">
          <Header />
          <div className="page-wrap">
            <main style={{ paddingTop: 36 }}>{children}</main>
          </div>
        </div>
      </body>
    </html>
  );
}