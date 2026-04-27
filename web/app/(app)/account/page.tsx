"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Check, X } from "lucide-react";

import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import { Separator } from "@/components/ui/separator";

type Me =
  | { signed_in: true; display_name: string; username: string; role: string }
  | { signed_in: false };

type Status =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "ok"; message: string }
  | { kind: "error"; message: string };

export default function AccountPage() {
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    fetch("/api/me", { credentials: "include" })
      .then((r) => r.json())
      .then((d: Me) => setMe(d))
      .catch(() => setMe({ signed_in: false }));
  }, []);

  if (me === null) {
    return (
      <main className="mx-auto max-w-2xl px-4 py-8">
        <Skeleton className="h-8 w-48 mb-6" />
        <Skeleton className="h-64 w-full mb-4" />
        <Skeleton className="h-64 w-full" />
      </main>
    );
  }

  if (!me.signed_in) {
    return (
      <main className="mx-auto max-w-md px-4 py-12 text-center">
        <p className="font-semibold">You are not signed in.</p>
        <Link href="/login" className={buttonVariants() + " mt-4"}>
          Go to login
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className={
            buttonVariants({ variant: "ghost", size: "sm" }) + " mb-3 -ml-2"
          }
        >
          <ArrowLeft className="mr-1 h-4 w-4" />
          Back to dashboard
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">Account settings</h1>
        <p className="text-muted-foreground text-sm">
          Manage your profile and password.
        </p>
      </div>

      <ProfileCard
        me={me}
        onSaved={(name) =>
          setMe({ ...me, display_name: name } as Me)
        }
      />
      <Separator className="my-6" />
      <PasswordCard />
    </main>
  );
}

function ProfileCard({
  me,
  onSaved,
}: {
  me: { signed_in: true; display_name: string; username: string; role: string };
  onSaved: (name: string) => void;
}) {
  const [name, setName] = useState(me.display_name);
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || name.trim() === me.display_name) return;
    setStatus({ kind: "saving" });
    try {
      const res = await fetch("/api/account/profile", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: name.trim() }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus({ kind: "error", message: data.error ?? `HTTP ${res.status}` });
        return;
      }
      onSaved(name.trim());
      setStatus({ kind: "ok", message: "Display name updated." });
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Network error",
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Profile</CardTitle>
        <CardDescription>
          Your display name appears throughout the app.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="grid gap-2 sm:grid-cols-2 sm:gap-4">
            <div className="space-y-2">
              <Label>Username</Label>
              <Input value={me.username} readOnly disabled />
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Input value={me.role} readOnly disabled />
            </div>
          </div>
          <div className="space-y-2">
            <Label htmlFor="display_name">Display name</Label>
            <Input
              id="display_name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={100}
              required
            />
          </div>
          <div className="flex items-center justify-between gap-3">
            <StatusLine status={status} />
            <Button
              type="submit"
              disabled={
                status.kind === "saving" ||
                !name.trim() ||
                name.trim() === me.display_name
              }
            >
              Save
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function PasswordCard() {
  const [oldPw, setOldPw] = useState("");
  const [newPw, setNewPw] = useState("");
  const [confirmPw, setConfirmPw] = useState("");
  const [status, setStatus] = useState<Status>({ kind: "idle" });

  const mismatch = confirmPw.length > 0 && newPw !== confirmPw;
  const tooShort = newPw.length > 0 && newPw.length < 8;
  const canSubmit =
    oldPw.length > 0 &&
    newPw.length >= 8 &&
    newPw === confirmPw &&
    status.kind !== "saving";

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    setStatus({ kind: "saving" });
    try {
      const res = await fetch("/api/account/password", {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ old_password: oldPw, new_password: newPw }),
      });
      const data = await res.json();
      if (!res.ok) {
        setStatus({ kind: "error", message: data.error ?? `HTTP ${res.status}` });
        return;
      }
      setOldPw("");
      setNewPw("");
      setConfirmPw("");
      setStatus({ kind: "ok", message: "Password updated." });
    } catch (e) {
      setStatus({
        kind: "error",
        message: e instanceof Error ? e.message : "Network error",
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
        <CardDescription>
          Use at least 8 characters. Sessions on other devices remain signed in
          until they expire.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <form className="space-y-4" onSubmit={onSubmit}>
          <div className="space-y-2">
            <Label htmlFor="old_password">Current password</Label>
            <Input
              id="old_password"
              type="password"
              autoComplete="current-password"
              value={oldPw}
              onChange={(e) => setOldPw(e.target.value)}
              required
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="new_password">New password</Label>
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              value={newPw}
              onChange={(e) => setNewPw(e.target.value)}
              required
            />
            {tooShort && (
              <p className="text-xs text-rose-600">
                Must be at least 8 characters.
              </p>
            )}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm_password">Confirm new password</Label>
            <Input
              id="confirm_password"
              type="password"
              autoComplete="new-password"
              value={confirmPw}
              onChange={(e) => setConfirmPw(e.target.value)}
              required
            />
            {mismatch && (
              <p className="text-xs text-rose-600">Passwords don&apos;t match.</p>
            )}
          </div>
          <div className="flex items-center justify-between gap-3">
            <StatusLine status={status} />
            <Button type="submit" disabled={!canSubmit}>
              Update password
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

function StatusLine({ status }: { status: Status }) {
  if (status.kind === "idle") return <span />;
  if (status.kind === "saving") {
    return (
      <span className="text-muted-foreground text-xs">Saving…</span>
    );
  }
  if (status.kind === "ok") {
    return (
      <span className="inline-flex items-center gap-1 text-emerald-600 text-xs">
        <Check className="h-3 w-3" />
        {status.message}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 text-rose-600 text-xs">
      <X className="h-3 w-3" />
      {status.message}
    </span>
  );
}
