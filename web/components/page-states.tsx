import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

export function NotSignedIn() {
  return (
    <div className="mx-auto max-w-md rounded-lg border border-dashed p-6 text-center text-sm">
      <p className="font-semibold">Sign in to CoachGPT</p>
      <p className="text-muted-foreground mt-1">
        Your session is required to view this page.
      </p>
      <Link href="/login" className={buttonVariants() + " mt-4"}>
        Go to login
      </Link>
    </div>
  );
}

export function ApiError({ message }: { message: string }) {
  return (
    <div className="mx-auto max-w-2xl rounded-lg border border-dashed p-6 text-sm">
      <p className="font-semibold">CoachGPT API error</p>
      <p className="text-muted-foreground mt-1 font-mono text-xs">{message}</p>
    </div>
  );
}

export function EmptyState({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mx-auto max-w-2xl rounded-lg border border-dashed p-6 text-center text-sm">
      <p className="font-semibold">{title}</p>
      <p className="text-muted-foreground mt-1">{description}</p>
    </div>
  );
}

export function LoadingList({ count = 6 }: { count?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className="h-20 w-full rounded-lg" />
      ))}
    </div>
  );
}
