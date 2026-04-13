export type ContactConfig = {
  phone?: string;
  tel_uri?: string;
  zalo_url?: string;
  facebook_url?: string;
  youtube_url?: string;
  zalo_oa_id?: string;
};

export type AuthZaloResponse = {
  user_type: "guest" | "tenant";
  access_token: string | null;
  user?: { id: number; name: string };
  error?: string;
};

export type MeResponse = {
  id: number;
  name: string;
  need_confirm_extend_contract?: boolean;
  error?: string;
};

export type EmptyRoomsResponse = {
  areas: Record<
    string,
    {
      id: number;
      name: string;
      houses: Record<
        string,
        {
          id: number;
          name: string;
          address?: string;
          rooms: Record<string, RoomInfo>;
        }
      >;
    }
  >;
};

export type RoomInfo = {
  id: number;
  house_name?: string;
  area_name?: string;
  name?: string;
  name_on_web?: string;
  main_image_url?: string;
  cur_price?: number;
  short_formatted_cur_price?: string;
  available_date?: string;
  website_note?: string;
  article?: string;
  images?: { id: number; url: string; mimetype?: string }[];
};

export type ContractItem = {
  id: number;
  name?: string;
  code?: string;
  status?: string;
  b_name?: string;
  b_id_number?: string;
  b_id_permanent_residence?: string;
  b_phone_number?: string;
  number_user?: number;
  start_date?: string | null;
  end_date?: string | null;
  deposit?: number;
  monthly_rental_price?: number;
  electricity_price_per_1kw?: number;
  fix_price_services?: {
    service_name?: string;
    price?: number;
    billing_unit?: string;
  }[];
};

export type InvoiceItem = {
  id: number;
  name?: string;
  status?: string;
  payment_label?: string;
  auto_note_html?: string;
  total_paid?: number;
  total_remain?: number;
  my_bank_name?: string | null;
  my_bank_account_no?: string | null;
  my_bank_account_name?: string | null;
  bank_qr_base64?: string | null;
};

export type TaskItem = {
  id: number;
  name?: string;
  note_html?: string;
  stage_name?: string | null;
  is_done?: boolean;
};

export type VehicleItem = {
  id: number;
  name?: string;
  type?: string;
  type_label?: string;
  license_plates?: string;
  action_status?: string;
  room_number?: string;
};
