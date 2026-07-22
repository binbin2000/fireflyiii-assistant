import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { auth } from "@/auth";
import { SignOutButton } from "@/components/auth/sign-out-button";
import { isOidcConfigured } from "@/lib/auth-status";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Firefly III Assistant",
  description: "A daily budgeting cockpit for Firefly III.",
};

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const session = isOidcConfigured() ? await auth() : null;

  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        {session?.user ? (
          <div className="flex justify-end px-6 pt-3">
            <SignOutButton label={session.user.email ?? session.user.name ?? "signed in"} />
          </div>
        ) : null}
        {children}
      </body>
    </html>
  );
}
