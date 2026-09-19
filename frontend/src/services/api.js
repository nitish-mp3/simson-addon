export async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    signal: options.signal || AbortSignal.timeout(15000),
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    const lower = text.toLowerCase();
    const proxyPage = lower.includes("<!doctype html") || lower.includes("<html") || lower.includes("cloudflare");
    data = {
      error: proxyPage
        ? `Service temporarily unavailable (HTTP ${res.status}). Check addon/VPS health and retry.`
        : (text || res.statusText || `Request failed: ${res.status}`).slice(0, 500),
      code: proxyPage ? "upstream_proxy_error" : "invalid_api_response",
    };
  }
  if (!res.ok) {
    const detail = Array.isArray(data.errors) && data.errors.length
      ? data.errors.join("; ")
      : data.error || data.message || `Request failed: ${res.status}`;
    const err = new Error(detail);
    err.data = data;
    err.status = res.status;
    throw err;
  }
  return data;
}
