/** Base URL của Odoo (không có dấu / cuối). Ví dụ: https://troxanh.example.com */
const raw = import.meta.env.VITE_API_BASE_URL || "";
export const API_BASE = raw.replace(/\/$/, "");

export const hasApiBase = (): boolean => Boolean(API_BASE);

export const apiUrl = (path: string): string => {
  const p = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE}${p}`;
};
