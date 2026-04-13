import { apiUrl, hasApiBase } from "./config";

export class ApiError extends Error {
  status: number;
  body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

async function parseJson(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export async function apiGet<T>(
  path: string,
  token?: string | null
): Promise<T> {
  if (!hasApiBase()) {
    throw new ApiError("Chưa cấu hình VITE_API_BASE_URL", 0, null);
  }
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(apiUrl(path), { headers });
  const data = await parseJson(res);
  if (!res.ok) {
    throw new ApiError(
      typeof data === "object" && data && "error" in (data as object)
        ? String((data as { error?: string }).error)
        : res.statusText,
      res.status,
      data
    );
  }
  return data as T;
}

export async function apiPost<T>(
  path: string,
  body: Record<string, unknown>,
  token?: string | null
): Promise<T> {
  if (!hasApiBase()) {
    throw new ApiError("Chưa cấu hình VITE_API_BASE_URL", 0, null);
  }
  const headers: Record<string, string> = {
    Accept: "application/json",
    "Content-Type": "application/json",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  const res = await fetch(apiUrl(path), {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  });
  const data = await parseJson(res);
  if (!res.ok) {
    throw new ApiError(
      typeof data === "object" && data && "error" in (data as object)
        ? String((data as { error?: string }).error)
        : res.statusText,
      res.status,
      data
    );
  }
  return data as T;
}
