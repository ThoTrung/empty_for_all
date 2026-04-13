import { useAtomValue, useSetAtom } from "jotai";
import {
  Box,
  Button,
  Icon,
  Input,
  List,
  Page,
  Spinner,
  Text,
} from "zmp-ui";
import { openChat } from "zmp-sdk/apis";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { apiGet, apiPost } from "@/api/client";
import { hasApiBase } from "@/api/config";
import type { AuthZaloResponse, ContactConfig } from "@/api/types";
import { useAuthBootstrap } from "@/hooks/useAuthBootstrap";
import { useZaloLogin } from "@/hooks/useZaloLogin";
import { saveJwt } from "@/lib/storage";
import { authReadyAtom, jwtAtom, meNameAtom, userTypeAtom } from "@/state/authAtoms";

function ProfilePage() {
  useAuthBootstrap();
  const navigate = useNavigate();
  const authReady = useAtomValue(authReadyAtom);
  const userType = useAtomValue(userTypeAtom);
  const meName = useAtomValue(meNameAtom);
  const jwt = useAtomValue(jwtAtom);
  const setJwt = useSetAtom(jwtAtom);
  const setUserType = useSetAtom(userTypeAtom);
  const setMeName = useSetAtom(meNameAtom);

  const { loading: loginLoading, error: loginErr, login } = useZaloLogin();
  const [cfg, setCfg] = useState<ContactConfig | null>(null);
  const [devPhone, setDevPhone] = useState("");
  const [devLoading, setDevLoading] = useState(false);
  const [devErr, setDevErr] = useState<string | null>(null);
  const allowLocalPhoneLogin = import.meta.env.DEV;
  const localPhoneAuthPath =
    import.meta.env.VITE_LOCAL_PHONE_AUTH_PATH || "/troxanh_zmini/api/v1/auth/dev_phone";

  useEffect(() => {
    if (!hasApiBase()) return;
    apiGet<ContactConfig>("/troxanh_zmini/api/v1/contact_config").then(setCfg);
  }, []);

  const logout = async () => {
    await saveJwt(null);
    setJwt(null);
    setMeName(null);
    setUserType("guest");
  };

  const consultAdmin = async () => {
    const oaId = cfg?.zalo_oa_id?.trim();
    if (!oaId) {
      return;
    }
    await openChat({
      type: "oa",
      id: oaId,
      message: "Xin chào, tôi muốn được tư vấn thuê phòng.",
    });
  };

  const loginWithDevPhone = async () => {
    const normalizedPhone = devPhone.replace(/\D/g, "");
    if (!normalizedPhone) {
      setDevErr("Vui lòng nhập số điện thoại.");
      return;
    }
    setDevErr(null);
    setDevLoading(true);
    try {
      const data = await apiPost<AuthZaloResponse>(localPhoneAuthPath, {
        phone: normalizedPhone,
      });
      if (data.user_type === "tenant" && data.access_token) {
        await saveJwt(data.access_token);
        setJwt(data.access_token);
        setMeName(data.user?.name ?? null);
        setUserType("tenant");
      } else {
        setDevErr(data.error || "Không tìm thấy khách hàng cho số điện thoại này.");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Đăng nhập local thất bại.";
      setDevErr(msg);
    } finally {
      setDevLoading(false);
    }
  };

  if (!authReady) {
    return (
      <Page>
        <Box className="flex justify-center items-center py-20">
          <Spinner />
        </Box>
      </Page>
    );
  }

  const isTenant = userType === "tenant" && jwt;

  return (
    <Page className="bg-background">
      <div className="p-4 space-y-4">
        <Text.Title size="large">Cá nhân</Text.Title>

        {!hasApiBase() && (
          <Box className="rounded-lg bg-amber-100 dark:bg-amber-900/30 p-3 text-sm">
            Cấu hình <code>VITE_API_BASE_URL</code> trỏ tới server Odoo (HTTPS).
          </Box>
        )}

        {isTenant ? (
          <>
            <Box className="rounded-xl bg-section p-4">
              <Text className="text-sm text-gray-500">Xin chào</Text>
              <Text className="text-lg font-semibold">{meName || "Khách"}</Text>
            </Box>
            <List>
              <List.Item
                onClick={() => navigate("/profile/contracts")}
                suffix={<Icon icon="zi-chevron-right" />}
              >
                Hợp đồng
              </List.Item>
              <List.Item
                onClick={() => navigate("/profile/invoices")}
                suffix={<Icon icon="zi-chevron-right" />}
              >
                Hóa đơn
              </List.Item>
              <List.Item
                onClick={() => navigate("/profile/tasks")}
                suffix={<Icon icon="zi-chevron-right" />}
              >
                Yêu cầu
              </List.Item>
              <List.Item
                onClick={() => navigate("/profile/vehicles")}
                suffix={<Icon icon="zi-chevron-right" />}
              >
                Đăng ký xe
              </List.Item>
            </List>
            <Button variant="secondary" fullWidth onClick={() => logout()}>
              Đăng xuất (thiết bị này)
            </Button>
          </>
        ) : (
          <Box className="space-y-3">
            <Text className="text-gray-600 dark:text-gray-300">
              Đăng nhập bằng số điện thoại Zalo để xem hợp đồng và hóa đơn nếu bạn
              đã đăng ký trên hệ thống.
            </Text>
            {loginErr && (
              <Text className="text-danger text-sm">{loginErr}</Text>
            )}
            <Button
              variant="primary"
              fullWidth
              loading={loginLoading}
              onClick={() => login()}
            >
              Đăng nhập với SĐT Zalo
            </Button>
            {allowLocalPhoneLogin && (
              <Box className="space-y-2 rounded-xl bg-section p-3">
                <Text size="small" className="text-gray-600 dark:text-gray-300">
                  Dev local: nhập SĐT khách hàng để test nhanh (không qua Zalo).
                </Text>
                <Input
                  type="text"
                  placeholder="Nhập số điện thoại khách hàng"
                  value={devPhone}
                  onChange={(e) => setDevPhone(e.target.value)}
                />
                {devErr && <Text className="text-danger text-sm">{devErr}</Text>}
                <Button
                  variant="secondary"
                  fullWidth
                  loading={devLoading}
                  onClick={loginWithDevPhone}
                >
                  Đăng nhập local bằng SĐT
                </Button>
              </Box>
            )}
            <Button
              variant="secondary"
              fullWidth
              onClick={() => consultAdmin()}
              disabled={!cfg?.zalo_oa_id}
            >
              Tư vấn qua Zalo OA
            </Button>
            {!cfg?.zalo_oa_id && hasApiBase() && (
              <Text size="xSmall" className="text-gray-500">
                Cấu hình OA: tham số hệ thống{" "}
                <code>troxanh_zmini.zalo_oa_id</code> trên Odoo.
              </Text>
            )}
          </Box>
        )}
      </div>
    </Page>
  );
}

export default ProfilePage;
