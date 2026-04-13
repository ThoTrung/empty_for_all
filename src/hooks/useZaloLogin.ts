import { useAtom, useSetAtom } from "jotai";
import { useCallback, useState } from "react";
import {
  authorize,
  getAccessToken,
  getPhoneNumber,
} from "zmp-sdk/apis";

import { apiPost } from "@/api/client";
import type { AuthZaloResponse } from "@/api/types";
import { saveJwt } from "@/lib/storage";
import { jwtAtom, meNameAtom, userTypeAtom } from "@/state/authAtoms";

export function useZaloLogin(): {
  loading: boolean;
  error: string | null;
  login: () => Promise<void>;
} {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [, setJwt] = useAtom(jwtAtom);
  const setUserType = useSetAtom(userTypeAtom);
  const setMeName = useSetAtom(meNameAtom);

  const login = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      await authorize({
        scopes: ["scope.userPhonenumber"],
      });
      const access_token = await getAccessToken();
      const { token: code } = await getPhoneNumber();
      if (!code) {
        throw new Error("Không lấy được mã số điện thoại từ Zalo.");
      }
      const data = await apiPost<AuthZaloResponse>(
        "/troxanh_zmini/api/v1/auth/zalo",
        { access_token, code }
      );
      if (data.user_type === "tenant" && data.access_token) {
        await saveJwt(data.access_token);
        setJwt(data.access_token);
        setMeName(data.user?.name ?? null);
        setUserType("tenant");
      } else {
        await saveJwt(null);
        setJwt(null);
        setMeName(null);
        setUserType("guest");
      }
    } catch (e) {
      const msg =
        e instanceof Error ? e.message : "Đăng nhập thất bại. Thử lại sau.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [setJwt, setMeName, setUserType]);

  return { loading, error, login };
}
