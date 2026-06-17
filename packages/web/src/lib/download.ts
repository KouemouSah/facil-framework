import { ApiError } from "@/lib/api";

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
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
