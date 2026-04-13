import { useEffect, useState } from "react";
import {
  Box,
  Button,
  Header,
  Page,
  Spinner,
  Text,
} from "zmp-ui";
import { useNavigate, useParams } from "react-router-dom";

import { apiGet } from "@/api/client";
import { hasApiBase } from "@/api/config";
import type { RoomInfo } from "@/api/types";

function RoomDetailPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [room, setRoom] = useState<RoomInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!hasApiBase() || !id) {
      setErr("Thiếu cấu hình hoặc mã phòng.");
      setLoading(false);
      return;
    }
    apiGet<RoomInfo>(`/troxanh_zmini/api/v1/room/${id}`)
      .then(setRoom)
      .catch(() => setErr("Không tải được thông tin phòng."))
      .finally(() => setLoading(false));
  }, [id]);

  return (
    <Page className="bg-background">
      <Header
        title="Chi tiết phòng"
        showBackIcon
        onBackClick={() => navigate(-1)}
      />
      <div className="p-4 pt-16 space-y-3 zmini-page-pad">
        {loading && (
          <Box className="flex justify-center py-12">
            <Spinner />
          </Box>
        )}
        {err && <Text className="text-danger">{err}</Text>}
        {room && (
          <>
            {room.main_image_url && (
              <img
                src={room.main_image_url}
                alt=""
                className="w-full rounded-xl object-cover max-h-56"
              />
            )}
            <Text.Title size="small">
              {room.name_on_web || room.name}
            </Text.Title>
            <Text className="text-gray-600 dark:text-gray-300">
              {room.area_name} · {room.house_name}
            </Text>
            {room.short_formatted_cur_price && (
              <Text className="text-primary font-semibold">
                {room.short_formatted_cur_price}
              </Text>
            )}
            {room.available_date && (
              <Text size="small">Ngày trống: {room.available_date}</Text>
            )}
            <Button
              variant="primary"
              fullWidth
              onClick={() => navigate("/profile")}
            >
              Tư vấn / Tài khoản
            </Button>
          </>
        )}
      </div>
    </Page>
  );
}

export default RoomDetailPage;
