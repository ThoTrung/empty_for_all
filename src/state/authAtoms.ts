import { atom } from "jotai";

export type UserType = "unknown" | "guest" | "tenant";

export const jwtAtom = atom<string | null>(null);
export const userTypeAtom = atom<UserType>("unknown");
export const meNameAtom = atom<string | null>(null);
export const authReadyAtom = atom(false);
