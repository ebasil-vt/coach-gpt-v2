"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronUp, LogOut, UserCog } from "lucide-react";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";

type Me =
  | { signed_in: true; display_name: string; username: string; role: string }
  | { signed_in: false };

export function UserMenu() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fetch("/api/me", { credentials: "include" })
      .then((r) => r.json())
      .then((d: Me) => setMe(d))
      .catch(() => setMe({ signed_in: false }));
  }, []);

  // Close on outside click + Escape
  useEffect(() => {
    if (!open) return;
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  if (me === null) return <Skeleton className="h-12 w-full rounded-md" />;

  if (!me.signed_in) {
    return (
      <Link
        href="/login"
        className={
          buttonVariants({ variant: "outline", size: "sm" }) +
          " w-full justify-start"
        }
      >
        Sign in
      </Link>
    );
  }

  const initials = me.display_name
    .split(/\s+/)
    .map((w) => w[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="group flex w-full items-center gap-2 rounded-md border border-transparent px-2 py-2 text-left transition-colors hover:bg-muted hover:border-border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-expanded={open}
        aria-haspopup="menu"
      >
        <Avatar className="h-8 w-8 shrink-0">
          <AvatarFallback className="text-xs">{initials}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 text-left">
          <div className="truncate text-xs font-semibold leading-tight">
            {me.display_name}
          </div>
          <div className="text-muted-foreground truncate text-[10px] leading-tight uppercase tracking-wider">
            {me.role}
          </div>
        </div>
        <ChevronUp
          className={`text-muted-foreground h-4 w-4 shrink-0 transition-transform ${open ? "" : "rotate-180"}`}
        />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute bottom-full left-0 right-0 z-50 mb-2 overflow-hidden rounded-lg border bg-popover text-popover-foreground shadow-lg"
        >
          <div className="border-b px-3 py-2">
            <div className="text-sm font-semibold">{me.display_name}</div>
            <div className="text-muted-foreground text-xs">@{me.username}</div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              router.push("/account");
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted"
          >
            <UserCog className="h-4 w-4" />
            Account settings
          </button>
          <div className="border-t" />
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              window.location.href = "/auth/logout";
            }}
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-rose-600 hover:bg-rose-500/10"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
