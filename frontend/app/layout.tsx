import type { Metadata, Viewport } from "next"
import type { ReactNode } from "react"
import { Geist, Geist_Mono } from "next/font/google"

import { Providers } from "@/components/providers"

import "./globals.css"

const sans = Geist({ variable: "--font-sans", subsets: ["latin"] })
const mono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] })

/** The browser tab's title and the page description. */
export const metadata: Metadata = {
  title: "Compilo · Compileits assistent",
  description: "Ställ frågor om Compileit och få svar med källor från compileit.com.",
}

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover", // lets the composer respect the iPhone home indicator (safe-area)
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0a0a0a" },
  ],
}

// Explicit props instead of Next's generated `LayoutProps`, which only exists after
// `next dev`/`next build` has run, so a clean checkout (CI) could not type-check.
export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    // next-themes sets the theme class before hydration, hence the suppressed warning.
    <html lang="sv" suppressHydrationWarning className={`${sans.variable} ${mono.variable}`}>
      <body className="antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
