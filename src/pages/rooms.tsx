import { useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Page,
  Spinner,
  Text,
} from "zmp-ui";
import { useNavigate } from "react-router-dom";

import { apiGet } from "@/api/client";
import { hasApiBase } from "@/api/config";
import type { EmptyRoomsResponse } from "@/api/types";
import { flattenEmptyRooms } from "@/lib/empty-rooms";

function RoomsPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<EmptyRoomsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!hasApiBase()) {
      setErr("Chưa cấu hình API.");
      setLoading(false);
      return;
    }
    apiGet<EmptyRoomsResponse>("/troxanh_zmini/api/v1/empty_rooms")
      .then(setData)
      .catch(() => setErr("Không tải được danh sách phòng."))
      .finally(() => setLoading(false));
  }, []);

  const flat = useMemo(
    () => (data ? flattenEmptyRooms(data) : []),
    [data]
  );

  return (
    <Page className="bg-background">
      <div className="p-4">
        <Text.Title size="large">Phòng trống</Text.Title>
        {loading && (
          <Box className="flex justify-center py-10">
            <Spinner />
          </Box>
        )}
        {err && (
          <Text className="text-danger py-4">{err}</Text>
        )}
        {!loading && !err && flat.length === 0 && (
          <Text className="text-gray-500 py-6">Hiện không có phòng trống.</Text>
        )}
        <div className="space-y-3">
          {flat.map((r) => (
            <Box
              key={r.id}
              className="zmini-room-card"
            >
              <div className="flex gap-3 items-start">
                <img
                  src={r.main_image_url}
                  alt=""
                  className="w-20 h-20 rounded-lg object-cover bg-gray-200"
                />
                <div className="flex-1 min-w-0">
                  <Text className="font-medium truncate">
                    {r.name_on_web || r.name}
                  </Text>
                  <Text size="xSmall" className="text-gray-500">
                    {r.house_name} · {r.area_name}
                  </Text>
                  {!!r.short_formatted_cur_price && (
                    <Text className="text-primary font-semibold">
                      {r.short_formatted_cur_price}
                    </Text>
                  )}
                  <Text size="xSmall" className="text-gray-500">
                    Trống: {r.available_date || "Cập nhật"}
                  </Text>
                </div>
              </div>
              <Button
                size="small"
                variant="primary"
                fullWidth
                className="mt-3"
                onClick={() => navigate(`/room/${r.id}`)}
              >
                Xem chi tiết
              </Button>
            </Box>
          ))}
        </div>
      </div>
    </Page>
  );
}

export default RoomsPage;
