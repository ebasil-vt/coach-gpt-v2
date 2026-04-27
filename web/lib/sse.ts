// Wire-format-aware reader for FastAPI's text/event-stream responses.
// Each event arrives as `data: <json>\n\n`. We parse out the JSON and yield
// progress objects to the caller.

export type StreamEvent = {
  type?: string;
  step?: string;
  message?: string;
  result?: unknown;
  error?: string;
  [k: string]: unknown;
};

export async function streamPost(
  path: string,
  body: FormData | object,
  onEvent: (e: StreamEvent) => void,
): Promise<void> {
  const init: RequestInit = {
    method: "POST",
    credentials: "include",
  };
  if (body instanceof FormData) {
    init.body = body;
  } else {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(body);
  }

  const res = await fetch(path, init);
  if (!res.ok || !res.body) {
    onEvent({ type: "error", error: `HTTP ${res.status}` });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let idx;
    while ((idx = buffer.indexOf("\n\n")) >= 0) {
      const chunk = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      for (const line of chunk.split("\n")) {
        if (!line.startsWith("data:")) continue;
        const payload = line.slice(5).trim();
        if (!payload) continue;
        try {
          onEvent(JSON.parse(payload) as StreamEvent);
        } catch {
          onEvent({ type: "raw", message: payload });
        }
      }
    }
  }
}
