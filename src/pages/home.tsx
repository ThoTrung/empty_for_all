import { useEffect, useMemo, useState } from "react";
import { Box, Button, Icon, Page, Swiper, Text } from "zmp-ui";
import { openChat, openPhone } from "zmp-sdk/apis";

import { apiGet } from "@/api/client";
import { hasApiBase } from "@/api/config";
import type { ContactConfig, EmptyRoomsResponse } from "@/api/types";
import { flattenEmptyRooms } from "@/lib/empty-rooms";
import { useNavigate } from "react-router-dom";

function HomePage() {
  const navigate = useNavigate();
  const [cfg, setCfg] = useState<ContactConfig | null>(null);
  const [roomsData, setRoomsData] = useState<EmptyRoomsResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!hasApiBase()) {
      setErr("Thiếu biến môi trường VITE_API_BASE_URL.");
      return;
    }
    apiGet<ContactConfig>("/troxanh_zmini/api/v1/contact_config")
      .then(setCfg)
      .catch(() => setErr("Không tải được cấu hình liên hệ."));

    apiGet<EmptyRoomsResponse>("/troxanh_zmini/api/v1/empty_rooms")
      .then(setRoomsData)
      .catch(() => {
        // Keep homepage usable even when rooms API is temporarily unavailable.
      });
  }, []);

  const flatRooms = useMemo(
    () => (roomsData ? flattenEmptyRooms(roomsData) : []),
    [roomsData]
  );

  const topRooms = useMemo(() => flatRooms.slice(0, 3), [flatRooms]);

  const overview = useMemo(() => {
    const areaSet = new Set<number>();
    const houseSet = new Set<number>();
    flatRooms.forEach((r) => {
      areaSet.add(r.area_id);
      houseSet.add(r.house_id);
    });
    return {
      rooms: flatRooms.length,
      areas: areaSet.size,
      houses: houseSet.size,
    };
  }, [flatRooms]);

  return (
    <Page className="bg-background text-foreground">
      <div className="p-4 space-y-4 zmini-page-pad zmini-home-template">
        <Box className="zmini-hero zmini-hero-doctor">
          <Text.Title size="small">
            Trọ Xanh <span className="text-sm font-normal">| Chào bạn</span>
          </Text.Title>
          <Text size="xSmall" className="text-gray-600">
            Quản lý thuê trọ nhanh chóng ngay trên Zalo Mini App
          </Text>
        </Box>

        <div className="zmini-search-wrap">
          <div className="zmini-search-input">
            <Icon icon="zi-search" />
            <span>Tìm phòng, tòa nhà, khu vực...</span>
          </div>
          <Button size="small" variant="primary" onClick={() => navigate("/rooms")}>
            Tìm
          </Button>
        </div>

        <div className="zmini-grid-3">
          <Box className="zmini-action-card" onClick={() => navigate("/rooms")}>
            <div className="zmini-action-icon zmini-bg-cyan">
              <Icon icon="zi-home" />
            </div>
            <Text className="font-medium">Đặt lịch</Text>
            <Text size="xSmall" className="text-gray-500">
              Xem phòng
            </Text>
          </Box>
          <Box className="zmini-action-card" onClick={() => navigate("/profile/tasks")}>
            <div className="zmini-action-icon zmini-bg-rose">
              <Icon icon="zi-clock-1" />
            </div>
            <Text className="font-medium">Lịch sử</Text>
            <Text size="xSmall" className="text-gray-500">
              Yêu cầu
            </Text>
          </Box>
          <Box className="zmini-action-card" onClick={() => navigate("/profile/contracts")}>
            <div className="zmini-action-icon zmini-bg-blue">
              <Icon icon="zi-note" />
            </div>
            <Text className="font-medium">Tài liệu</Text>
            <Text size="xSmall" className="text-gray-500">
              Hợp đồng
            </Text>
          </Box>
        </div>

        <div className="zmini-quick-row">
          <button className="zmini-quick-item" onClick={() => navigate("/profile")}>
            <Icon icon="zi-user-circle" />
            <span>Cá nhân</span>
          </button>
          <button className="zmini-quick-item" onClick={() => navigate("/rooms")}>
            <Icon icon="zi-list" />
            <span>Danh mục</span>
          </button>
          <button className="zmini-quick-item" onClick={() => navigate("/profile/invoices")}>
            <Icon icon="zi-wallet" />
            <span>Hóa đơn</span>
          </button>
          <button className="zmini-quick-item" onClick={() => navigate("/news")}>
            <Icon icon="zi-chat" />
            <span>Tin tức</span>
          </button>
          <button className="zmini-quick-item" onClick={() => navigate("/profile/vehicles")}>
            <Icon icon="zi-more-grid" />
            <span>Tất cả</span>
          </button>
        </div>

        <Box className="zmini-section zmini-highlight-block">
          <div className="zmini-sec-head">
            <Text className="font-semibold">Dịch vụ nổi bật</Text>
            <button className="zmini-link-btn" onClick={() => navigate("/rooms")}>
              Xem tất cả
            </button>
          </div>
          <div className="zmini-highlight-grid">
            <Box className="zmini-feature-card zmini-feature-main">
              <Text className="font-semibold">Phòng trống</Text>
              <Text size="xSmall">Cập nhật theo thời gian thực</Text>
              <Text className="zmini-pill">XEM</Text>
              <Text className="zmini-feature-number">{overview.rooms}</Text>
            </Box>
            <Box className="zmini-feature-card zmini-feature-sub">
              <Text className="font-semibold">Tòa nhà</Text>
              <Text size="xSmall">{overview.houses} địa điểm hoạt động</Text>
            </Box>
            <Box className="zmini-feature-card zmini-feature-sub2">
              <Text className="font-semibold">Khu vực</Text>
              <Text size="xSmall">{overview.areas} khu vực đang có phòng</Text>
            </Box>
          </div>
        </Box>

        <Box className="zmini-section">
          <Text className="font-semibold pb-2">Hỗ trợ nhanh</Text>
          <div className="grid grid-cols-2 gap-2">
            <Box className="zmini-mini-card">
              <Icon icon="zi-call" />
              <div>
                <Text className="font-medium">Tư vấn</Text>
                <Text size="xSmall" className="text-gray-500">
                  Chat với quản trị
                </Text>
              </div>
            </Box>
            <Box className="zmini-mini-card">
              <Icon icon="zi-home" />
              <div>
                <Text className="font-medium">Xem phòng</Text>
                <Text size="xSmall" className="text-gray-500">
                  Đặt lịch linh hoạt
                </Text>
              </div>
            </Box>
          </div>
        </Box>

        <Box className="zmini-section">
          <div className="zmini-sec-head">
            <Text className="font-semibold">Phòng mới cập nhật</Text>
            <button className="zmini-link-btn" onClick={() => navigate("/rooms")}>
              Xem tất cả
            </button>
          </div>
          <div className="space-y-2">
            {topRooms.length === 0 && (
              <Text size="xSmall" className="text-gray-500">
                Chưa có dữ liệu phòng. Dữ liệu sẽ lấy từ Odoo khi đã kết nối API.
              </Text>
            )}
            {topRooms.map((r) => (
              <Box key={`home-room-${r.id}`} className="zmini-room-inline">
                <img
                  src={r.main_image_url}
                  alt=""
                  className="w-16 h-16 rounded-lg object-cover bg-gray-200"
                />
                <div className="flex-1 min-w-0">
                  <Text className="font-medium truncate">
                    {r.name_on_web || r.name}
                  </Text>
                  <Text size="xSmall" className="text-gray-500">
                    {r.house_name} · {r.area_name}
                  </Text>
                </div>
                <Button
                  size="small"
                  variant="secondary"
                  onClick={() => navigate(`/room/${r.id}`)}
                >
                  Xem
                </Button>
              </Box>
            ))}
          </div>
        </Box>

        <Swiper autoplay duration={2500} className="rounded-xl">
          <Swiper.Slide key="s1">
            <Box className="zmini-banner zmini-banner-1">
              <Text className="font-semibold">Phòng trống cập nhật liên tục</Text>
              <Text size="xSmall">Xem giá, ngày trống, tiện ích rõ ràng</Text>
            </Box>
          </Swiper.Slide>
          <Swiper.Slide key="s2">
            <Box className="zmini-banner zmini-banner-2">
              <Text className="font-semibold">Hóa đơn hàng tháng minh bạch</Text>
              <Text size="xSmall">Theo dõi thanh toán ngay trong mini app</Text>
            </Box>
          </Swiper.Slide>
        </Swiper>

        {err && (
          <Box className="rounded-lg bg-amber-100 dark:bg-amber-900/40 p-3 text-sm">
            {err}
          </Box>
        )}

        {cfg?.phone && (
          <Box className="rounded-xl bg-section p-4 space-y-2">
            <Text className="font-medium">Liên hệ</Text>
            <Button
              variant="tertiary"
              fullWidth
              onClick={() =>
                openPhone({
                  phoneNumber: cfg.phone!.replace(/\s/g, ""),
                })
              }
            >
              Gọi {cfg.phone}
            </Button>
            <Button
              variant="primary"
              fullWidth
              onClick={() => {
                if (cfg?.zalo_oa_id) {
                  openChat({
                    type: "oa",
                    id: cfg.zalo_oa_id,
                    message: "Xin chào, tôi cần tư vấn thuê phòng.",
                  });
                }
              }}
              disabled={!cfg?.zalo_oa_id}
            >
              Chat tư vấn ngay
            </Button>
          </Box>
        )}
      </div>
    </Page>
  );
}

export default HomePage;
