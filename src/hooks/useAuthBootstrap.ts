import { useSetAtom } from "jotai";
import { useEffect } from "react";

import { apiGet } from "@/api/client";
import { hasApiBase } from "@/api/config";
import type { MeResponse } from "@/api/types";
import { loadJwt } from "@/lib/storage";
import { authReadyAtom, jwtAtom, meNameAtom, userTypeAtom } from "@/state/authAtoms";

/** Khôi phục JWT từ storage và xác thực /me khi mở app. */
export function useAuthBootstrap(): void {
  const setJwt = useSetAtom(jwtAtom);
  const setUserType = useSetAtom(userTypeAtom);
  const setMeName = useSetAtom(meNameAtom);
  const setReady = useSetAtom(authReadyAtom);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!hasApiBase()) {
        setUserType("guest");
        setReady(true);
        return;
      }
      const stored = await loadJwt();
      if (cancelled) return;
      if (!stored) {
        setUserType("guest");
        setReady(true);
        return;
      }
      setJwt(stored);
      try {
        const me = await apiGet<MeResponse>("/troxanh_zmini/api/v1/me", stored);
        if (cancelled) return;
        setMeName(me.name);
        setUserType("tenant");
      } catch {
        if (cancelled) return;
        setJwt(null);
        setUserType("guest");
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setJwt, setMeName, setReady, setUserType]);
}
