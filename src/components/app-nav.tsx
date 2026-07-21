"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const links = [
  { href: "/", label: "Budgets" },
  { href: "/transactions", label: "Transactions" },
];

export function AppNav() {
  const pathname = usePathname();

  return (
    <nav className="inline-flex gap-1 rounded-md border border-slate-200 bg-slate-50 p-1">
      {links.map((link) => (
        <Link
          key={link.href}
          href={link.href}
          className={cn(
            "h-8 rounded px-3 text-sm font-semibold leading-8 transition",
            pathname === link.href
              ? "bg-white text-slate-950 shadow-sm"
              : "text-slate-500 hover:text-slate-800",
          )}
        >
          {link.label}
        </Link>
      ))}
    </nav>
  );
}
