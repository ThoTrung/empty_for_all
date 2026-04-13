import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Box, Header, List, Page, Spinner, Text } from "zmp-ui";
import { useNavigate } from "react-router-dom";

import { apiGet } from "@/api/client";
import type { ContractItem } from "@/api/types";
import { jwtAtom } from "@/state/authAtoms";

type Resp = { contracts: ContractItem[] };

function ProfileContractsPage() {
  const navigate = useNavigate();
  const jwt = useAtomValue(jwtAtom);
  const [data, setData] = useState<ContractItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!jwt) {
      setErr("Chưa đăng nhập.");
      setLoading(false);
      return;
    }
    apiGet<Resp>("/troxanh_zmini/api/v1/contracts", jwt)
      .then((r) => setData(r.contracts))
      .catch(() => setErr("Không tải được hợp đồng."))
      .finally(() => setLoading(false));
  }, [jwt]);

  return (
    <Page>
      <Header
        title="Hợp đồng"
        showBackIcon
        onBackClick={() => navigate(-1)}
      />
      <div className="p-4 pt-16 zmini-page-pad">
        {loading && (
          <Box className="flex justify-center py-10">
            <Spinner />
          </Box>
        )}
        {err && <Text className="text-danger">{err}</Text>}
        {data && data.length === 0 && (
          <Text className="text-gray-500 py-4">Chưa có hợp đồng.</Text>
        )}
        <List>
          {data?.map((c) => (
            <List.Item key={c.id}>
              <div className="space-y-1 w-full">
                <Text className="font-medium">{c.name || c.code}</Text>
                <Text size="xSmall" className="text-gray-500">
                  {c.status} · {c.start_date} → {c.end_date}
                </Text>
                <Text size="xSmall">
                  Tiền thuê: {c.monthly_rental_price?.toLocaleString("vi-VN")} ·
                  Cọc: {c.deposit?.toLocaleString("vi-VN")}
                </Text>
              </div>
            </List.Item>
          ))}
        </List>
      </div>
    </Page>
  );
}

export default ProfileContractsPage;
