import type { EmptyRoomsResponse, RoomInfo } from "@/api/types";

export type FlatRoom = RoomInfo & {
  area_name: string;
  house_name: string;
  house_id: number;
  area_id: number;
};

/** Gom cấu trúc Odoo area → house → room thành danh sách phẳng cho UI. */
export function flattenEmptyRooms(data: EmptyRoomsResponse): FlatRoom[] {
  const out: FlatRoom[] = [];
  const areas = data.areas || {};
  for (const area of Object.values(areas)) {
    const houses = area.houses || {};
    for (const house of Object.values(houses)) {
      const rooms = house.rooms || {};
      for (const room of Object.values(rooms)) {
        out.push({
          ...room,
          area_name: area.name || "",
          house_name: house.name || "",
          house_id: house.id,
          area_id: area.id,
        });
      }
    }
  }
  return out;
}
