export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === "string" ? detail : detail?.code || `http_${status}`);
    this.status = status;
    this.detail = detail;
  }
}

export async function api(path, options = {}) {
  const opts = { credentials: "same-origin", ...options };
  if (opts.body !== undefined && typeof opts.body !== "string") {
    opts.headers = { "Content-Type": "application/json", ...(opts.headers || {}) };
    opts.body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, opts);
  let data = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = text;
    }
  }
  if (!res.ok) {
    throw new ApiError(res.status, data?.detail ?? data);
  }
  return data;
}

export const post = (path, body) => api(path, { method: "POST", body });
export const put = (path, body) => api(path, { method: "PUT", body });
export const del = (path) => api(path, { method: "DELETE" });

export function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(seconds)) return "—";
  const s = Math.max(0, Math.round(seconds));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  const rem = s % 60;
  if (m < 60) return rem ? `${m}m ${rem}s` : `${m}m`;
  const h = Math.floor(m / 60);
  return `${h}h ${m % 60}m`;
}

export function formatTime(iso, locale = "en-PH", timeZone) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleTimeString(locale, {
      hour: "2-digit",
      minute: "2-digit",
      timeZone,
    });
  } catch {
    return "—";
  }
}

export function formatDate(iso, locale = "en-PH", timeZone) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString(locale, {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone,
    });
  } catch {
    return "—";
  }
}
