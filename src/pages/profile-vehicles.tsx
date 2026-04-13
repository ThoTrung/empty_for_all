import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Box, Header, List, Page, Spinner, Text } from "zmp-ui";
import { useNavigate } from "react-router-dom";

import { apiGet } from "@/api/client";
import type { VehicleItem } from "@/api/types";
import { jwtAtom } from "@/state/authAtoms";

type Resp = { vehicles: VehicleItem[]; house_vehicles: VehicleItem[] };

function ProfileVehiclesPage() {
  const navigate = useNavigate();
  const jwt = useAtomValue(jwtAtom);
  const [data, setData] = useState<Resp | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!jwt) {
      setErr("Chưa đăng nhập.");
      setLoading(false);
      return;
    }
    apiGet<Resp>("/troxanh_zmini/api/v1/vehicles", jwt)
      .then(setData)
      .catch(() => setErr("Không tải được thông tin xe."))
      .finally(() => setLoading(false));
  }, [jwt]);

  return (
    <Page>
      <Header
        title="Xe"
        showBackIcon
        onBackClick={() => navigate(-1)}
      />
      <div className="p-4 pt-16 space-y-4 zmini-page-pad">
        {loading && (
          <Box className="flex justify-center py-10">
            <Spinner />
          </Box>
        )}
        {err && <Text className="text-danger">{err}</Text>}
        <Text className="font-medium">Xe của bạn</Text>
        {data?.vehicles?.length === 0 && (
          <Text className="text-gray-500 text-sm">Chưa đăng ký xe.</Text>
        )}
        <List>
          {data?.vehicles?.map((v) => (
            <List.Item key={v.id}>
              <div>
                <Text className="font-medium">{v.license_plates}</Text>
                <Text size="xSmall" className="text-gray-500">
                  {v.type_label} · {v.action_status}
                </Text>
              </div>
            </List.Item>
          ))}
        </List>
        <Text className="font-medium pt-2">Xe trong nhà (đã duyệt)</Text>
        <List>
          {data?.house_vehicles?.map((v, i) => (
            <List.Item key={`h-${i}-${v.id}`}>
              <Text size="small">
                Phòng {v.room_number} · {v.type_label} · {v.license_plates}
              </Text>
            </List.Item>
          ))}
        </List>
      </div>
    </Page>
  );
}

export default ProfileVehiclesPage;
