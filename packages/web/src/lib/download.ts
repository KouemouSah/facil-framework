import { ApiError } from "@/lib/api";
import { sanitizeFilename } from "@/lib/sanitize";

/**
 * Download a backend file (e.g. CSV export) through the BFF as a blob, then
 * trigger a client-side save with `filename`. The BFF attaches the auth cookie
 * server-side and forwards Content-Type; the filename is set here (the BFF does
 * not forward Content-Disposition). 401 -> redirect to login (mirrors apiFetch).
 */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const res = await fetch(`/api/bff${path}`, { credentials: "same-origin" });
  if (res.status === 401 && typeof window !== "undefined") {
    window.location.assign("/login");
    throw new ApiError(401, "session expired");
  }
  if (!res.ok) throw new ApiError(res.status, "export failed");

  // Never save an active-content type as a file (an exfil/XSS-on-open risk if the
  // backend or a proxy mislabels the body). Exports are csv/xlsx/octet-stream.
  const ct = (res.headers.get("content-type") || "").toLowerCase();
  if (/text\/html|javascript|xml/.test(ct)) {
    throw new ApiError(415, "unexpected export content type");
  }

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  try {
    const a = document.createElement("a");
    a.href = url;
    a.download = sanitizeFilename(filename); // anti-traversal / illegal chars
    document.body.appendChild(a);
    a.click();
    a.remove();
  } finally {
    URL.revokeObjectURL(url); // always release, even if the click throws
  }
}
