export type ApiResult<T> =
  | { kind: "ok"; data: T }
  | { kind: "unauthorized" }
  | { kind: "error"; message: string };

export async function apiGet<T>(path: string): Promise<ApiResult<T>> {
  try {
    const res = await fetch(path, { credentials: "include" });
    if (res.status === 401) return { kind: "unauthorized" };
    if (!res.ok) return { kind: "error", message: `HTTP ${res.status}` };
    return { kind: "ok", data: (await res.json()) as T };
  } catch (e) {
    return {
      kind: "error",
      message: e instanceof Error ? e.message : "Network error",
    };
  }
}

export async function apiPost<T>(
  path: string,
  body?: unknown,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(path, {
      method: "POST",
      credentials: "include",
      headers: body ? { "Content-Type": "application/json" } : undefined,
      body: body ? JSON.stringify(body) : undefined,
    });
    if (res.status === 401) return { kind: "unauthorized" };
    if (!res.ok) {
      try {
        const data = (await res.json()) as { error?: string };
        return { kind: "error", message: data.error ?? `HTTP ${res.status}` };
      } catch {
        return { kind: "error", message: `HTTP ${res.status}` };
      }
    }
    return { kind: "ok", data: (await res.json()) as T };
  } catch (e) {
    return {
      kind: "error",
      message: e instanceof Error ? e.message : "Network error",
    };
  }
}

export async function apiPostForm<T>(
  path: string,
  formData: FormData,
): Promise<ApiResult<T>> {
  try {
    const res = await fetch(path, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    if (res.status === 401) return { kind: "unauthorized" };
    if (!res.ok) {
      try {
        const data = (await res.json()) as { error?: string };
        return { kind: "error", message: data.error ?? `HTTP ${res.status}` };
      } catch {
        return { kind: "error", message: `HTTP ${res.status}` };
      }
    }
    return { kind: "ok", data: (await res.json()) as T };
  } catch (e) {
    return {
      kind: "error",
      message: e instanceof Error ? e.message : "Network error",
    };
  }
}
