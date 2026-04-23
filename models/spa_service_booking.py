# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo import api, fields, models, _
from markupsafe import Markup, escape
from odoo.exceptions import ValidationError, UserError


class SpaServiceBooking(models.Model):
    _name = "spa.service.booking"
    _description = "Đặt lịch dịch vụ"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_datetime asc, id desc"

    name = fields.Char(string="Mã đặt lịch", readonly=True, copy=False)
    calendar_event_title = fields.Char(
        string="Tiêu đề lịch",
        compute="_compute_calendar_event_title",
        store=False,
        help="Mã đặt lịch + tên khách hàng, dùng làm tiêu đề ô sự kiện trên calendar.",
    )
    partner_id = fields.Many2one(
        "res.partner",
        string="Khách hàng",
        required=True,
        tracking=True,
    )
    # Một dropdown cho nhân viên: mỗi giá trị ánh xạ tới completion_res_* (cách B).
    # Thêm loại mới: bổ sung key trong Selection + nhánh trong _compute_completion_pointer
    # + model triển khai spa_complete_booking (inherit spa.booking.completion.mixin).
    booking_kind = fields.Selection(
        selection=[
            ("card", "Sử dụng thẻ trị liệu"),
            (
                "non_session",
                "Không trừ buổi thẻ — họp, tư vấn, đi học…",
            ),
        ],
        string="Hình thức lịch",
        default="card",
        required=True,
        tracking=True,
        help="Chọn hình thức trước, sau đó chọn thẻ hoặc loại hoạt động tương ứng.",
    )
    non_session_offering_id = fields.Many2one(
        "spa.booking.non_session_offering",
        string="Loại hoạt động",
        ondelete="restrict",
        tracking=True,
        domain="[('active', '=', True)]",
        help="Dùng khi lịch không trừ buổi trên thẻ (danh mục cấu hình được).",
    )
    completion_res_model_id = fields.Many2one(
        "ir.model",
        string="Model xử lý hoàn thành",
        compute="_compute_completion_pointer",
        store=True,
        index=True,
    )
    completion_res_id = fields.Integer(
        string="ID bản ghi xử lý",
        compute="_compute_completion_pointer",
        store=True,
    )
    product_id = fields.Many2one(
        "product.product",
        string="Dịch vụ",
        required=False,
        domain=[("detailed_type", "=", "service")],
        tracking=True,
    )
    start_datetime = fields.Datetime(string="Bắt đầu", required=True, tracking=True)
    duration = fields.Integer(
        string="Thời gian (phút)",
        default=60,
        required=True,
        tracking=True,
        help="Thời gian dịch vụ (phút). Mặc định từ thẻ/dịch vụ. Thời gian kết thúc = Bắt đầu + Thời gian.",
    )
    end_datetime = fields.Datetime(
        string="Kết thúc",
        compute="_compute_end_datetime",
        store=True,
        readonly=False,
        inverse="_inverse_end_datetime",
        tracking=True,
    )
    staff_id = fields.Many2one(
        "res.users",
        string="Nhân viên phụ trách",
        required=False,
        default=lambda self: self.env.user,
        tracking=True,
        help="Bắt buộc khi đặt lịch thường. Không bắt buộc khi tạo chuỗi theo ngày trong tuần (điền sau).",
    )
    staff_ids = fields.Many2many(
        "res.users",
        "spa_service_booking_staff_rel",
        "booking_id",
        "user_id",
        string="Nhân viên thực hiện",
        domain=[("share", "=", False)],
        tracking=True,
        help="Nhiều nhân viên có thể cùng thực hiện dịch vụ. Khi chỉ có 1 người, hệ thống vẫn tương thích với staff_id cũ.",
    )

    suggested_staff_html = fields.Html(
        string="Nhân viên gợi ý (luân ca)",
        compute="_compute_suggested_staff_html",
        store=False,
        sanitize=False,
    )
    staff_level_filter = fields.Selection(
        selection=[
            ("regular", "Nhân viên"),
            ("expert", "Chuyên gia"),
        ],
        string="Cấp độ nhân viên",
        compute="_compute_staff_level_filter",
        store=False,
        help="Giá trị phục vụ bộ lọc checkbox trên calendar (Nhân viên / Chuyên gia).",
    )
    # Màu trên calendar: theo trạng thái (HEX cấu hình trong Cấu hình Spa)
    state_calendar_hex_color = fields.Char(
        string="Màu HEX lịch (theo trạng thái)",
        compute="_compute_state_calendar_hex_color",
        store=False,
        readonly=True,
    )
    state_calendar_hex_text_color = fields.Char(
        string="Màu HEX chữ lịch (theo trạng thái)",
        compute="_compute_state_calendar_hex_text_color",
        store=False,
        readonly=True,
    )
    draft_special_hex_color = fields.Char(
        string="Màu HEX đặc biệt (draft)",
        compute="_compute_draft_special_colors",
        store=False,
        readonly=True,
    )
    draft_special_hex_text_color = fields.Char(
        string="Màu HEX chữ đặc biệt (draft)",
        compute="_compute_draft_special_colors",
        store=False,
        readonly=True,
    )
    # Giữ lại theo giường cho form/report nếu cần
    bed_calendar_color = fields.Integer(
        string="Màu lịch (theo giường)",
        compute="_compute_bed_calendar_color",
        store=False,
        readonly=True,
    )

    @api.depends("start_datetime", "duration")
    def _compute_end_datetime(self):
        for rec in self:
            if rec.start_datetime and rec.duration is not None and rec.duration > 0:
                rec.end_datetime = rec.start_datetime + timedelta(minutes=rec.duration)
            else:
                rec.end_datetime = rec.start_datetime

    @api.model
    def _spa_staff_booking_count_on_local_day(self, user_id, local_day, exclude_booking_id=None):
        """
        Số lượng đặt lịch trùng ngày local_day mà NV tham gia (staff_ids hoặc booking_line_ids.staff_id).
        Mỗi booking chỉ tính một lần — kể cả draft hay chỉ chiếm 20% capacity (vẫn là một lịch đã gán).
        Chỉ loại trừ cancel. exclude_booking_id: bản ghi đang sửa không tính.
        """
        day_start = datetime.combine(local_day, datetime.min.time())
        day_end = day_start + timedelta(days=1)
        dom = [
            ("state", "!=", "cancel"),
            ("start_datetime", "<", day_end),
            ("end_datetime", ">", day_start),
            "|",
            ("staff_ids", "in", [user_id]),
            ("booking_line_ids.staff_id", "=", user_id),
        ]
        if exclude_booking_id:
            dom.append(("id", "!=", exclude_booking_id))
        return self.search_count(dom)

    @api.model
    def _spa_rotation_ordered_staff_ids(self, product_id, start_datetime, end_datetime, booking_id=None):
        """
        Thứ tự gợi ý / quay vòng (trong các NV đủ điều kiện slot hiện tại):

        1) Ít lịch đặt trong ngày (local) hơn trước — đếm số booking (mọi state trừ cancel, gồm draft)
           mà NV tham gia; mỗi booking tính 1 dù chỉ 20% capacity. Booking đang sửa không tính.
        2) Ca bắt đầu sớm hơn (giờ:phút) trước ca muộn hơn.
        3) spa_staff_sequence, rồi id.
        """
        if not start_datetime or not end_datetime:
            return []
        available = self.get_available_staff_ids(
            product_id, start_datetime, end_datetime, booking_id=booking_id
        )
        if not available:
            return []

        local_start = fields.Datetime.context_timestamp(self, start_datetime) or start_datetime
        if getattr(local_start, "tzinfo", None):
            local_start = local_start.replace(tzinfo=None)
        local_day = local_start.date()
        prev_day = local_day - timedelta(days=1)
        ShiftCfg = self.env["booking.shift.config"]
        shift_map_today = ShiftCfg.get_user_shift_map_for_date(local_day)
        shift_map_prev = ShiftCfg.get_user_shift_map_for_date(prev_day)

        def _shift_start_hours_for_order(user):
            st, dur = shift_map_today.get(user.id, (None, None))
            if dur is not None and dur > 0:
                return float(st)
            stp, durp = shift_map_prev.get(user.id, (None, None))
            if durp is not None and durp > 0:
                return float(stp)
            return 999.0

        rows = []
        for user in available:
            day_booking_count = self._spa_staff_booking_count_on_local_day(
                user.id, local_day, exclude_booking_id=booking_id
            )
            st_h = _shift_start_hours_for_order(user)
            seq = user.spa_staff_sequence or 0
            # Tuple: (số lịch trong ngày tăng dần → ít lịch ưu tiên trước, ca sớm, sequence, id)
            rows.append((day_booking_count, st_h, seq, user.id))
        rows.sort(key=lambda r: (r[0], r[1], r[2], r[3]))
        return [r[3] for r in rows]

    def _spa_rotation_ordered_staff_ids_by_history(self, product_id, start_dt, end_dt, booking_id=None):
        """Gợi ý / thứ tự luân ca (alias tên cũ)."""
        if not product_id or not start_dt or not end_dt:
            return []
        return self._spa_rotation_ordered_staff_ids(
            product_id, start_dt, end_dt, booking_id=booking_id
        )

    @api.depends(
        "booking_kind",
        "product_id",
        "card_id",
        "non_session_offering_id",
        "start_datetime",
        "end_datetime",
        "duration",
        "staff_ids",
    )
    def _compute_suggested_staff_html(self):
        for rec in self:
            # Nếu form chưa đủ thông tin slot thì không render gợi ý.
            if not rec.start_datetime or not rec.end_datetime:
                rec.suggested_staff_html = ""
                continue

            product_id = False
            if rec.booking_kind == "card" and rec.card_id and rec.card_id.product_id:
                product_id = rec.card_id.product_id.id
            elif rec.booking_kind == "non_session" and rec.non_session_offering_id and rec.non_session_offering_id.product_id:
                product_id = rec.non_session_offering_id.product_id.id
            elif rec.product_id:
                product_id = rec.product_id.id

            ordered_ids = rec._spa_rotation_ordered_staff_ids_by_history(
                product_id=product_id,
                start_dt=rec.start_datetime,
                end_dt=rec.end_datetime,
                booking_id=rec.id,
            )
            if not ordered_ids:
                rec.suggested_staff_html = Markup("<i>Không có nhân viên phù hợp</i>")
                continue

            staffs = self.env["res.users"].browse(ordered_ids)
            first_id = ordered_ids[0] if ordered_ids else False

            items = []
            for uid in ordered_ids:
                staff = staffs.filtered(lambda s: s.id == uid)
                staff = staff[:1]
                if not staff:
                    continue
                is_first = uid == first_id
                css = "active" if is_first else ""
                items.append(
                    f'<li class="list-group-item {css}">'
                    f'{escape(staff[0].name or staff[0].login)}'
                    f"</li>"
                )

            html = (
                '<div class="o_spa_suggested_staff">'
                '<label><b>Gợi ý:</b></label>'
                '<ul class="list-group list-group-flush mt-1">'
                + "".join(items)
                + "</ul></div>"
            )
            rec.suggested_staff_html = Markup(html)

    @api.onchange(
        "booking_kind",
        "product_id",
        "card_id",
        "non_session_offering_id",
        "start_datetime",
        "duration",
        "end_datetime",
    )
    def _onchange_set_staff_from_suggested(self):
        """Nếu staff_ids đang trống thì tự chọn nhân viên gợi ý đầu tiên."""
        if self.state not in ("draft", False):
            return
        if self.staff_ids:
            return
        if not self.start_datetime or not self.end_datetime:
            return

        product_id = False
        if self.booking_kind == "card" and self.card_id and self.card_id.product_id:
            product_id = self.card_id.product_id.id
        elif (
            self.booking_kind == "non_session"
            and self.non_session_offering_id
            and self.non_session_offering_id.product_id
        ):
            product_id = self.non_session_offering_id.product_id.id
        elif self.product_id:
            product_id = self.product_id.id

        ordered_ids = self._spa_rotation_ordered_staff_ids_by_history(
            product_id=product_id,
            start_dt=self.start_datetime,
            end_dt=self.end_datetime,
            booking_id=self.id,
        )
        if ordered_ids:
            self.staff_ids = [(6, 0, [ordered_ids[0]])]

    def _inverse_end_datetime(self):
        """Khi sửa giờ kết thúc (vd. kéo thả lịch), cập nhật duration (phút)."""
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime > rec.start_datetime:
                delta = rec.end_datetime - rec.start_datetime
                rec.duration = int(round(delta.total_seconds() / 60.0))

    @api.depends(
        "partner_id",
        "partner_id.name",
        "partner_id.customer_code",
        "partner_id.phone",
        "partner_id.mobile",
        "staff_ids",
        "staff_ids.name",
        "staff_ids.spa_staff_nickname",
        "card_id",
        "card_id.code",
        "card_id.product_id",
        "card_id.product_id.default_code",
        "card_id.product_id.name",
        "booking_kind",
        "non_session_offering_id",
        "non_session_offering_id.name",
        "non_session_offering_id.product_id",
        "non_session_offering_id.product_id.default_code",
        "non_session_offering_id.product_id.name",
        "booking_line_ids",
        "booking_line_ids.product_id",
        "booking_line_ids.product_id.default_code",
        "booking_line_ids.product_id.name",
    )
    def _compute_calendar_event_title(self):
        for rec in self:
            def _join_code_name(code, name):
                code = (code or "").strip()
                name = (name or "").strip()
                if code and name:
                    return f"{code} - {name}"
                return code or name or ""

            # Nickname staff (first staff for compact display)
            nick = ""
            staff_users = rec.staff_ids
            if staff_users and isinstance(staff_users, models.BaseModel):
                staff0 = staff_users[:1]
                nick = (staff0.spa_staff_nickname or staff0.name or "").strip()

            # Customer: Name (phone)
            cust = ""
            if rec.partner_id:
                phone = (rec.partner_id.phone or rec.partner_id.mobile or "").strip()
                name = (rec.partner_id.name or rec.partner_id.display_name or "").strip()
                if phone and name:
                    cust = f"{name} ({phone})"
                else:
                    cust = name or phone

            # Service: Code - Name
            # - Nếu có `card_id` -> lấy từ thẻ (giữ nguyên logic cũ)
            # - Nếu `card_id` rỗng -> lấy từ `non_session_offering_id` (Đi họp/Đi học/...)
            # - Fallback: lấy từ `product_id` nếu thiếu cả 2 trường trên
            if rec.card_id:
                card = rec.card_id
                card_product = card.product_id if card else rec.product_id
                service_code = (card.code if card else "") or (
                    card_product.default_code if card_product else ""
                )
                service_name = (
                    card_product.name or card_product.display_name if card_product else ""
                )
                service_line = _join_code_name(service_code, service_name)
            elif rec.non_session_offering_id:
                off = rec.non_session_offering_id
                off_product = off.product_id or rec.product_id
                service_code = (off.code or "") or (
                    off_product.default_code if off_product else ""
                )
                service_name = (
                    off.name
                    or off_product.name
                    or off_product.display_name
                    if off_product
                    else ""
                )
                service_line = _join_code_name(service_code, service_name)
            else:
                p = rec.product_id
                service_code = p.default_code if p else ""
                service_name = p.name or p.display_name if p else ""
                service_line = _join_code_name(service_code, service_name)

            # One-line title that can wrap when the cell is narrow:
            # (Nickname) Customer (phone) ServiceCode - ServiceName
            parts = []
            if nick:
                parts.append(f"({nick})")
            if cust:
                parts.append(cust)
            if service_line:
                parts.append(service_line)
            rec.calendar_event_title = " ".join([p for p in parts if p])

    @api.depends("staff_ids", "staff_ids.spa_staff_level")
    def _compute_staff_level_filter(self):
        """Trả về 1 giá trị để Odoo Calendar có thể render checkbox lọc."""
        for rec in self:
            level = ""
            # ưu tiên expert nếu có trong danh sách
            staff_users = rec.staff_ids
            if staff_users:
                if isinstance(staff_users, models.BaseModel):
                    levels = set(staff_users.mapped("spa_staff_level"))
                    if "expert" in levels:
                        level = "expert"
                    elif "regular" in levels:
                        level = "regular"
                else:
                    # many2one
                    lvl = getattr(staff_users, "spa_staff_level", "") or ""
                    level = lvl
            rec.staff_level_filter = level

    def _get_calendar_hex_color_for_state(self, state):
        """Màu HEX cho trạng thái, đọc từ Cấu hình Spa. Có thể để trống."""
        ICP = self.env["ir.config_parameter"].sudo()
        key = "spa.booking_calendar_hex_color_%s" % (state or "draft")
        val = (ICP.get_param(key, "") or "").strip()
        if not val:
            return ""
        if not val.startswith("#"):
            val = f"#{val}"
        return val

    def _get_calendar_hex_text_color_for_state(self, state):
        """Màu HEX chữ cho trạng thái, đọc từ Cấu hình Spa. Có thể để trống."""
        ICP = self.env["ir.config_parameter"].sudo()
        key = "spa.booking_calendar_hex_text_color_%s" % (state or "draft")
        val = (ICP.get_param(key, "") or "").strip()
        if not val:
            return ""
        if not val.startswith("#"):
            val = f"#{val}"
        return val

    @api.model
    def _spa_pick_text_color_bw(self, bg_hex):
        """Trả về #FFFFFF hoặc #000000 theo contrast; bg_hex có thể #rgb/#rrggbb."""
        val = (bg_hex or "").strip()
        if not val:
            return ""
        if not val.startswith("#"):
            val = f"#{val}"
        h = val[1:]
        if len(h) == 3:
            h = "".join([c * 2 for c in h])
        try:
            r = int(h[0:2], 16)
            g = int(h[2:4], 16)
            b = int(h[4:6], 16)
        except Exception:
            return ""

        def srgb_to_lin(c):
            c = c / 255.0
            return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

        L = 0.2126 * srgb_to_lin(r) + 0.7152 * srgb_to_lin(g) + 0.0722 * srgb_to_lin(b)
        # Contrast ratio vs white (1.0) and black (0.0)
        c_white = (1.0 + 0.05) / (L + 0.05)
        c_black = (L + 0.05) / (0.0 + 0.05)
        return "#FFFFFF" if c_white >= c_black else "#000000"

    def _spa_local_date_from_datetime(self, dt):
        if not dt:
            return None
        local = fields.Datetime.context_timestamp(self, dt) or dt
        if getattr(local, "tzinfo", None):
            local = local.replace(tzinfo=None)
        return local.date()

    def _spa_get_product_template_for_draft_color(self):
        self.ensure_one()
        # Prefer product_id; fallback to card/non_session offering when product_id is missing.
        product_variant = self.product_id
        if not product_variant and self.card_id and getattr(self.card_id, "product_id", False):
            product_variant = self.card_id.product_id
        elif (
            not product_variant
            and self.non_session_offering_id
            and getattr(self.non_session_offering_id, "product_id", False)
        ):
            product_variant = self.non_session_offering_id.product_id
        return product_variant.product_tmpl_id if product_variant and product_variant.product_tmpl_id else False

    @api.depends("state")
    def _compute_state_calendar_hex_color(self):
        for rec in self:
            rec.state_calendar_hex_color = rec._get_calendar_hex_color_for_state(rec.state)

    @api.depends("state")
    def _compute_state_calendar_hex_text_color(self):
        for rec in self:
            rec.state_calendar_hex_text_color = rec._get_calendar_hex_text_color_for_state(
                rec.state
            )

    @api.depends(
        "state",
        "booking_kind",
        "non_session_offering_id",
        "recurring_parent_id",
        "recurring_is_active",
        "create_date",
        "product_id",
        "card_id",
        "card_id.product_id",
        "non_session_offering_id.product_id",
    )
    def _compute_draft_special_colors(self):
        """
        Chỉ áp dụng cho state=draft. Priority (cao → thấp):
          1) non_session (họp/đào tạo/mẫu)
          2) lịch cố định hàng tuần (đặt theo tuần)
          3) triệt lông (product.template.spa_booking_is_hair_removal)
          4) dịch vụ chuyên gia (spa_required_staff_level='expert')
          5) khách mới đặt nhưng create_date là quá khứ (khác hôm nay)
        """
        ICP = self.env["ir.config_parameter"].sudo()
        try:
            hair_categ_id = int(ICP.get_param("spa.booking_calendar_hair_removal_category_id", "0") or "0")
        except (TypeError, ValueError):
            hair_categ_id = 0
        hair_categ_ids = set()
        if hair_categ_id:
            hair_categ_ids = set(
                self.env["product.category"]
                .sudo()
                .search([("id", "child_of", hair_categ_id)])
                .ids
            )
        cfg = {
            "weekly": ICP.get_param("spa.booking_calendar_hex_color_draft_weekly", "#3E51BA"),
            "past": ICP.get_param("spa.booking_calendar_hex_color_draft_past_created", "#33B577"),
            "non_session": ICP.get_param("spa.booking_calendar_hex_color_draft_non_session", "#D71629"),
            "hair": ICP.get_param("spa.booking_calendar_hex_color_draft_hair_removal", "#F44F15"),
            "expert": ICP.get_param("spa.booking_calendar_hex_color_draft_expert_only", "#8E24AC"),
        }
        cfg_txt = {
            "weekly": ICP.get_param("spa.booking_calendar_hex_text_color_draft_weekly", ""),
            "past": ICP.get_param("spa.booking_calendar_hex_text_color_draft_past_created", ""),
            "non_session": ICP.get_param("spa.booking_calendar_hex_text_color_draft_non_session", ""),
            "hair": ICP.get_param("spa.booking_calendar_hex_text_color_draft_hair_removal", ""),
            "expert": ICP.get_param("spa.booking_calendar_hex_text_color_draft_expert_only", ""),
        }
        for rec in self:
            rec.draft_special_hex_color = ""
            rec.draft_special_hex_text_color = ""
            if rec.state != "draft":
                continue

            def norm(v):
                v = (v or "").strip()
                if not v:
                    return ""
                return v if v.startswith("#") else f"#{v}"

            chosen = ""
            chosen_key = ""
            # 1) non_session
            if rec.booking_kind == "non_session":
                chosen = norm(cfg["non_session"])
                chosen_key = "non_session"
            # 2) weekly recurring
            elif rec.recurring_parent_id or rec.recurring_is_active:
                chosen = norm(cfg["weekly"])
                chosen_key = "weekly"
            else:
                pt = rec._spa_get_product_template_for_draft_color()
                # 3) hair removal
                if pt and pt.categ_id and pt.categ_id.id in hair_categ_ids:
                    chosen = norm(cfg["hair"])
                    chosen_key = "hair"
                # 4) expert only
                elif pt and (getattr(pt, "spa_required_staff_level", "") or "") == "expert":
                    chosen = norm(cfg["expert"])
                    chosen_key = "expert"
                else:
                    # 5) created in the past (not today)
                    today = fields.Date.context_today(rec)
                    created_day = rec._spa_local_date_from_datetime(rec.create_date)
                    if created_day and created_day < today:
                        chosen = norm(cfg["past"])
                        chosen_key = "past"

            if chosen:
                rec.draft_special_hex_color = chosen
                cfg_text = norm(cfg_txt.get(chosen_key, "")) if chosen_key else ""
                rec.draft_special_hex_text_color = cfg_text or rec._spa_pick_text_color_bw(
                    chosen
                )

    @api.depends("bed_id", "bed_id.calendar_color", "state")
    def _compute_bed_calendar_color(self):
        for rec in self:
            if rec.state == "cancel":
                rec.bed_calendar_color = 0
            else:
                rec.bed_calendar_color = rec.bed_id.calendar_color if rec.bed_id else 0

    bed_id = fields.Many2one(
        "spa.bed",
        string="Giường / máy",
        required=False,
        tracking=True,
        help="Bắt buộc khi đặt lịch thường. Không bắt buộc khi tạo chuỗi theo ngày trong tuần (điền sau).",
    )
    # --- Đặt theo tuần (recurring) ---
    recurring_parent_id = fields.Many2one(
        "spa.service.booking",
        string="Thuộc chuỗi đặt theo tuần",
        ondelete="cascade",
        copy=False,
        index=True,
    )
    recurring_child_ids = fields.One2many(
        "spa.service.booking",
        "recurring_parent_id",
        string="Các lịch theo tuần",
        copy=False,
    )
    recurring_enabled = fields.Boolean(
        string="Bật đặt theo tuần",
        default=False,
        copy=False,
        help="Bật để hiện tuỳ chọn ngày trong tuần ngay trong form.",
    )
    recurring_is_active = fields.Boolean(
        string="Đã tạo lịch theo tuần",
        default=False,
        copy=False,
        help="True khi đã tạo chuỗi đặt lịch theo tuần cho thẻ này.",
    )
    recurring_mon = fields.Boolean(string="Thứ 2", default=False, copy=False)
    recurring_tue = fields.Boolean(string="Thứ 3", default=False, copy=False)
    recurring_wed = fields.Boolean(string="Thứ 4", default=False, copy=False)
    recurring_thu = fields.Boolean(string="Thứ 5", default=False, copy=False)
    recurring_fri = fields.Boolean(string="Thứ 6", default=False, copy=False)
    recurring_sat = fields.Boolean(string="Thứ 7", default=False, copy=False)
    recurring_sun = fields.Boolean(string="CN", default=False, copy=False)
    is_recurring_child = fields.Boolean(
        string="Là lịch con theo tuần",
        compute="_compute_is_recurring_child",
        store=False,
    )

    @api.depends("recurring_parent_id")
    def _compute_is_recurring_child(self):
        for rec in self:
            rec.is_recurring_child = bool(rec.recurring_parent_id)
    booking_line_ids = fields.One2many(
        "spa.service.booking.line",
        "booking_id",
        string="Dịch vụ con",
        copy=True,
        help="Chỉ dùng khi đặt lịch dịch vụ tổng (nhiều dịch vụ con). Mỗi dòng: dịch vụ, nhân viên, thời gian. Check rảnh/capacity theo từng dòng.",
    )
    is_composite_booking = fields.Boolean(
        string="Là đặt lịch dịch vụ tổng",
        compute="_compute_is_composite_booking",
        store=True,
    )

    @api.depends("booking_line_ids")
    def _compute_is_composite_booking(self):
        for rec in self:
            rec.is_composite_booking = bool(rec.booking_line_ids)
    card_id = fields.Many2one(
        "spa.treatment.card",
        string="Thẻ trị liệu",
        required=False,
        help="Thẻ trị liệu dùng cho buổi đặt lịch (khi hình thức là thẻ).",
        tracking=True,
    )
    card_total_sessions = fields.Integer(
        string="Tổng số buổi",
        related="card_id.total_sessions",
        readonly=True,
    )
    card_available_for_booking = fields.Integer(
        string="Còn cho đặt lịch",
        related="card_id.available_for_booking",
        readonly=True,
    )
    session_id = fields.Many2one(
        "spa.treatment.session",
        string="Buổi trị liệu",
        readonly=True,
        help="Tạo khi KH đến làm dịch vụ (từ thẻ hoặc không).",
        tracking=True,
    )
    state = fields.Selection(
        [
            ("draft", "Đặt lịch"),
            ("confirmed", "Đã xác nhận"),
            ("doing", "Đang phục vụ"),
            ("done", "Đã hoàn thành"),
            ("cancel", "Đã hủy"),
        ],
        string="Trạng thái",
        default="draft",
        required=True,
        tracking=True,
    )
    reminder_sent = fields.Boolean(
        string="Đã nhắc nhân viên",
        default=False,
        copy=False,
    )
    note = fields.Text(string="Ghi chú")
    is_locked = fields.Boolean(
        string="Khóa sửa",
        compute="_compute_is_locked",
        help="True khi buổi trị liệu đã hoàn thành hoặc đã hủy.",
    )

    @api.depends("session_id", "session_id.state")
    def _compute_is_locked(self):
        for rec in self:
            rec.is_locked = bool(
                rec.session_id and rec.session_id.state in ("done", "cancel")
            )

    @api.onchange("card_id")
    def _onchange_card_id_duration(self):
        if self.card_id and self.card_id.duration_minutes:
            self.duration = self.card_id.duration_minutes

    @api.onchange("booking_kind")
    def _onchange_booking_kind(self):
        if self.booking_kind == "card":
            self.non_session_offering_id = False
        elif self.booking_kind == "non_session":
            self.card_id = False

    @api.onchange("non_session_offering_id")
    def _onchange_non_session_offering_id_duration(self):
        if self.non_session_offering_id and self.non_session_offering_id.duration_minutes:
            self.duration = self.non_session_offering_id.duration_minutes

    @api.depends("booking_kind", "card_id", "non_session_offering_id")
    def _compute_completion_pointer(self):
        Im = self.env["ir.model"].sudo()
        im_card = Im._get("spa.treatment.card")
        im_ns = Im._get("spa.booking.non_session_offering")
        for rec in self:
            if rec.booking_kind == "card" and rec.card_id:
                rec.completion_res_model_id = im_card
                rec.completion_res_id = rec.card_id.id
            elif rec.booking_kind == "non_session" and rec.non_session_offering_id:
                rec.completion_res_model_id = im_ns
                rec.completion_res_id = rec.non_session_offering_id.id
            else:
                rec.completion_res_model_id = False
                rec.completion_res_id = 0

    def _get_completion_target(self):
        """Bản ghi nhận delegation spa_complete_booking (cách B)."""
        self.ensure_one()
        if not self.completion_res_model_id or not self.completion_res_id:
            return self.env["spa.treatment.card"]
        model = self.completion_res_model_id.model
        target = self.env[model].browse(self.completion_res_id)
        return target if target.exists() else self.env[model]

    # -----------------------
    # Recurring (inline)
    # -----------------------
    def action_enable_recurring(self):
        """Bật tuỳ chọn đặt theo tuần (hiện checkbox trong form)."""
        self.ensure_one()
        if self.is_locked or self.is_recurring_child:
            return
        self.write({"recurring_enabled": True})

    def _get_selected_weekdays(self):
        """Return set {0..6} tương ứng thứ 2..CN."""
        self.ensure_one()
        mapping = [
            ("recurring_mon", 0),
            ("recurring_tue", 1),
            ("recurring_wed", 2),
            ("recurring_thu", 3),
            ("recurring_fri", 4),
            ("recurring_sat", 5),
            ("recurring_sun", 6),
        ]
        return {wd for fname, wd in mapping if getattr(self, fname)}

    def _unlink_future_recurring_children(self):
        """Xoá các lịch con ở tương lai chưa dùng (chưa tạo session)."""
        self.ensure_one()
        now = fields.Datetime.now()
        children = self.recurring_child_ids.filtered(
            lambda b: (not b.session_id)
            and b.state in ("draft", "confirmed")
            and b.start_datetime
            and b.start_datetime >= now
        )
        if children:
            children.unlink()

    def action_confirm_recurring(self):
        """Tạo/đổi lịch theo tuần: xoá lịch tương lai cũ rồi tạo lại theo ngày đã chọn."""
        self.ensure_one()
        if self.is_locked or self.is_recurring_child:
            return
        if self.booking_kind != "card":
            raise UserError(_("Đặt lịch theo tuần chỉ dùng khi hình thức là « Sử dụng thẻ trị liệu »."))
        if not self.partner_id or not self.card_id or not self.start_datetime:
            raise UserError(_("Vui lòng chọn Khách hàng, Thẻ trị liệu và thời gian bắt đầu."))
        weekdays = self._get_selected_weekdays()
        if not weekdays:
            raise UserError(_("Vui lòng chọn ít nhất một ngày trong tuần."))

        # 1) Xoá lịch tương lai cũ (nếu có)
        self._unlink_future_recurring_children()

        # 2) Đồng bộ ngày bắt đầu của booking hiện tại sang ngày đầu tiên phù hợp
        base_dt = fields.Datetime.to_datetime(self.start_datetime)
        base_date = base_dt.date()
        start_time = base_dt.time().replace(second=0, microsecond=0)

        # Tìm ngày đầu tiên >= base_date nằm trong weekdays
        current = base_date
        for _i in range(0, 366):
            if current.weekday() in weekdays:
                break
            current += timedelta(days=1)
        new_start_dt = datetime.combine(current, start_time)
        if new_start_dt != base_dt:
            self.write({"start_datetime": new_start_dt})

        # 3) Tạo thêm các booking con cho đủ số buổi còn có thể đặt
        #    (card.available_for_booking đã trừ booking hiện tại và các booking khác đang giữ thẻ)
        self.card_id.invalidate_recordset(["reserved_by_bookings", "available_for_booking"])
        additional = self.card_id.available_for_booking
        if additional <= 0:
            # vẫn đánh dấu active để cho phép huỷ/đổi trong trường hợp đã có lịch khác giữ thẻ
            self.write({"recurring_enabled": True, "recurring_is_active": True})
            return

        duration = self.card_id.duration_minutes or self.duration or 60
        Booking = self.env["spa.service.booking"]
        created = 0
        current = fields.Datetime.to_datetime(self.start_datetime).date()
        # bắt đầu từ ngày tiếp theo để tránh trùng với booking hiện tại
        current += timedelta(days=1)
        for _i in range(0, 366):
            if created >= additional:
                break
            if current.weekday() in weekdays:
                start_dt = datetime.combine(current, start_time)
                Booking.create({
                    "partner_id": self.partner_id.id,
                    "booking_kind": "card",
                    "card_id": self.card_id.id,
                    "product_id": self.card_id.product_id.id if self.card_id.product_id else self.product_id.id,
                    "start_datetime": start_dt,
                    "duration": duration,
                    "bed_id": False,
                    "recurring_parent_id": self.id,
                })
                created += 1
            current += timedelta(days=1)

        self.write({"recurring_enabled": True, "recurring_is_active": True})

    def action_cancel_recurring(self):
        """Huỷ lịch theo tuần: xoá các lịch con ở tương lai chưa dùng, tắt UI recurring."""
        self.ensure_one()
        if self.is_locked or self.is_recurring_child:
            return
        self._unlink_future_recurring_children()
        self.write({
            "recurring_is_active": False,
            "recurring_enabled": False,
            "recurring_mon": False,
            "recurring_tue": False,
            "recurring_wed": False,
            "recurring_thu": False,
            "recurring_fri": False,
            "recurring_sat": False,
            "recurring_sun": False,
        })

    @api.constrains("duration")
    def _check_duration(self):
        for rec in self:
            if rec.duration is not None and rec.duration <= 0:
                raise ValidationError(_("Thời gian (giờ) phải lớn hơn 0."))

    @api.constrains("start_datetime", "end_datetime")
    def _check_datetime(self):
        for rec in self:
            if rec.start_datetime and rec.end_datetime and rec.end_datetime <= rec.start_datetime:
                raise ValidationError(_("Thời gian kết thúc phải sau thời gian bắt đầu."))

    def _get_staff_capacity_usages(self):
        """Trả về list (staff_id, start, end, capacity_percent) cho booking này. Dùng cho check capacity."""
        self.ensure_one()
        usages = []
        if self.booking_line_ids:
            for line in self.booking_line_ids:
                if not line.staff_id or not line.start_datetime or not line.end_datetime:
                    continue
                cap = line._get_capacity_percent()
                usages.append((line.staff_id.id, line.start_datetime, line.end_datetime, cap))
        else:
            if self.staff_ids and self.start_datetime and self.end_datetime:
                # Capacity % của booking đơn:
                # - Ưu tiên theo `product_id` nếu có
                # - Nếu `product_id` đang NULL (thường gặp khi booking tạo từ `card_id`),
                #   thì lấy theo `card_id.product_id` (hoặc non_session_offering).
                cap = 100
                product_variant = self.product_id
                if not product_variant and self.card_id and getattr(self.card_id, "product_id", False):
                    product_variant = self.card_id.product_id
                elif not product_variant and self.non_session_offering_id and getattr(self.non_session_offering_id, "product_id", False):
                    product_variant = self.non_session_offering_id.product_id

                if product_variant and product_variant.product_tmpl_id:
                    pt = product_variant.product_tmpl_id
                    if getattr(pt, "spa_staff_capacity_percent", None):
                        cap = max(1, min(100, pt.spa_staff_capacity_percent))
                staff_users = self.staff_ids
                for user in staff_users:
                    usages.append((user.id, self.start_datetime, self.end_datetime, cap))
        return usages

    @api.constrains("start_datetime", "end_datetime", "staff_ids", "state", "booking_line_ids")
    def _check_staff_conflict(self):
        """Kiểm tra theo capacity %: tổng % các đặt lịch cùng nhân viên trong cùng khung giờ không vượt 100%."""
        for rec in self:
            if rec.state == "cancel":
                continue
            # Check staff shift window: chỉ theo booking.shift.config theo từng ngày (không dùng giờ ca trên User).
            # duration=0 trên dòng ca => nghỉ ngày đó.
            ShiftCfg = self.env["booking.shift.config"]

            def _within_shift(user, start_dt, end_dt):
                if not start_dt or not end_dt:
                    return True
                local_start = fields.Datetime.context_timestamp(self, start_dt) or start_dt
                local_end = fields.Datetime.context_timestamp(self, end_dt) or end_dt
                if getattr(local_start, "tzinfo", None):
                    local_start = local_start.replace(tzinfo=None)
                if getattr(local_end, "tzinfo", None):
                    local_end = local_end.replace(tzinfo=None)

                day_local = local_start.date()
                prev_day = day_local - timedelta(days=1)
                map_today = ShiftCfg.get_user_shift_map_for_date(day_local)
                map_prev = ShiftCfg.get_user_shift_map_for_date(prev_day)

                def _get_shift(shift_day):
                    if shift_day == day_local and user.id in map_today:
                        return map_today[user.id]
                    if shift_day == prev_day and user.id in map_prev:
                        return map_prev[user.id]
                    return None, None

                def _check_for_day(shift_day):
                    st_hours, duration_hours = _get_shift(shift_day)
                    if st_hours is None or duration_hours is None:
                        return False
                    if duration_hours <= 0:
                        return False
                    if st_hours < 0 or st_hours >= 24:
                        return False
                    shift_start = datetime.combine(
                        shift_day, datetime.min.time()
                    ) + timedelta(hours=st_hours)
                    shift_end = shift_start + timedelta(hours=duration_hours)
                    return local_start >= shift_start and local_end <= shift_end

                return _check_for_day(day_local) or _check_for_day(prev_day)

            for user in rec.staff_ids:
                if not _within_shift(user, rec.start_datetime, rec.end_datetime):
                    raise ValidationError(
                        _(
                            "Nhân viên %s không thuộc ca làm đã cấu hình cho ngày này.",
                            user.name,
                        )
                    )
            for line in rec.booking_line_ids:
                if line.staff_id and line.start_datetime and line.end_datetime:
                    if not _within_shift(line.staff_id, line.start_datetime, line.end_datetime):
                        raise ValidationError(
                            _(
                                "Nhân viên %s không thuộc ca làm đã cấu hình cho ngày này.",
                                line.staff_id.name,
                            )
                        )

            usages = rec._get_staff_capacity_usages()
            for staff_id, start, end, cap in usages:
                total = rec._sum_staff_capacity_in_range(staff_id, start, end, exclude_booking_id=rec.id)
                if total + cap > 100:
                    staff = self.env["res.users"].browse(staff_id)
                    raise ValidationError(
                        _(
                            "Nhân viên %s vượt 100%% năng lực trong khoảng thời gian này (hiện %s%%, thêm %s%%).",
                            staff.name,
                            total,
                            cap,
                        )
                    )

    def _sum_staff_capacity_in_range(self, staff_id, start_dt, end_dt, exclude_booking_id=None):
        """Tổng % capacity đã dùng của staff_id trong (start_dt, end_dt), từ các booking khác (và lines)."""
        Booking = self.env["spa.service.booking"]
        total = 0
        domain = [
            ("state", "not in", ["cancel"]),
        ]
        # Narrow by time range for performance
        if start_dt and end_dt:
            domain += [
                ("start_datetime", "<", end_dt),
                ("end_datetime", ">", start_dt),
            ]
        if exclude_booking_id:
            domain.append(("id", "!=", exclude_booking_id))
        # Only bookings involving this staff (direct or in many2many or in composite lines)
        # Dùng OR vì booking có thể:
        # - Gắn staff trực tiếp qua `staff_ids` (booking đơn)
        # - Hoặc gắn staff qua `booking_line_ids.staff_id` (booking composite)
        domain += [
            "|",
            ("staff_ids", "in", [staff_id]),
            ("booking_line_ids.staff_id", "=", staff_id),
        ]
        for booking in Booking.search(domain):
            for sid, s, e, cap in booking._get_staff_capacity_usages():
                if sid != staff_id:
                    continue
                if s and e and start_dt and end_dt and s < end_dt and e > start_dt:
                    total += cap
        return min(100, total)

    @api.constrains("booking_kind", "card_id", "non_session_offering_id")
    def _check_booking_completion_target(self):
        for rec in self:
            if rec.booking_kind == "card":
                if not rec.card_id:
                    raise ValidationError(
                        _("Với « Sử dụng thẻ trị liệu », vui lòng chọn thẻ.")
                    )
            elif rec.booking_kind == "non_session":
                if not rec.non_session_offering_id:
                    raise ValidationError(
                        _(
                            "Với « Không trừ buổi thẻ », vui lòng chọn loại hoạt động "
                            "(danh mục cấu hình)."
                        )
                    )

    @api.constrains("start_datetime", "end_datetime", "bed_id", "state")
    def _check_bed_conflict(self):
        """Giường/máy không trùng lịch trong cùng khoảng thời gian."""
        for rec in self:
            # Cho phép các booking trạng thái draft trùng thời gian (phục vụ giữ chỗ trong UI),
            # chỉ kiểm tra xung đột khi booking đã "thực sự" vào chu trình phục vụ.
            if rec.state in ("cancel", "draft") or not rec.bed_id:
                continue
            if not rec.start_datetime or not rec.end_datetime:
                continue
            overlap = self.search_count([
                ("id", "!=", rec.id),
                ("bed_id", "=", rec.bed_id.id),
                ("state", "in", ["confirmed", "doing", "done"]),
                ("start_datetime", "<", rec.end_datetime),
                ("end_datetime", ">", rec.start_datetime),
            ])
            if overlap:
                raise ValidationError(
                    _("Giường/máy %s đã được đặt trong khoảng thời gian này.", rec.bed_id.name)
                )

    def _prepare_create_values(self, vals_list):
        """Sau khi default_get thêm default_end_datetime từ context (calendar 1h),
        bỏ end_datetime và cố định duration từ thẻ để inverse không ghi đè duration."""
        had_card = [vals.get("card_id") for vals in vals_list]
        result = super()._prepare_create_values(vals_list)
        for vals, card_id in zip(result, had_card):
            if card_id:
                card = self.env["spa.treatment.card"].browse(card_id)
                if card.exists() and card.duration_minutes:
                    vals["duration"] = card.duration_minutes
                    vals.pop("end_datetime", None)
        return result

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = self.env["ir.sequence"].next_by_code("spa.service.booking") or _("New")
            # Khi có thẻ: luôn lấy duration từ thẻ (form/calendar có thể gửi duration=60 hoặc không gửi duration)
            if vals.get("card_id"):
                card = self.env["spa.treatment.card"].browse(vals["card_id"])
                if card.exists() and card.duration_minutes:
                    vals["duration"] = card.duration_minutes
                    vals.pop("end_datetime", None)
            if vals.get("non_session_offering_id"):
                off = self.env["spa.booking.non_session_offering"].browse(
                    vals["non_session_offering_id"]
                )
                if off.exists() and off.duration_minutes:
                    vals["duration"] = off.duration_minutes
                    vals.pop("end_datetime", None)
            # Khi tạo từ calendar (chọn khoảng), có thể chỉ có start + end → suy ra duration
            start = vals.get("start_datetime")
            end = vals.get("end_datetime")
            duration = vals.get("duration")
            if start and end and (duration is None or duration <= 0):
                try:
                    delta = end - start
                    if hasattr(delta, "total_seconds"):
                        vals["duration"] = max(int(round(delta.total_seconds() / 60.0)), 15)
                except (TypeError, ValueError):
                    pass
        result = super().create(vals_list)
        card_ids = [v.get("card_id") for v in vals_list if v.get("card_id")]
        if card_ids:
            self.env["spa.treatment.card"].browse(card_ids).invalidate_recordset(
                ["reserved_by_bookings", "available_for_booking"]
            )
        return result

    def write(self, vals):
        # Khi có thẻ (mới chọn hoặc đổi thẻ): luôn đồng bộ duration từ thẻ và bỏ end_datetime
        # để tránh client gửi end_datetime/duration cũ (60p) → inverse ghi đè duration
        if vals.get("card_id"):
            card = self.env["spa.treatment.card"].browse(vals["card_id"])
            if card.exists() and card.duration_minutes:
                vals = dict(vals, duration=card.duration_minutes)
                vals.pop("end_datetime", None)
        if vals.get("non_session_offering_id"):
            off = self.env["spa.booking.non_session_offering"].browse(
                vals["non_session_offering_id"]
            )
            if off.exists() and off.duration_minutes:
                vals = dict(vals, duration=off.duration_minutes)
                vals.pop("end_datetime", None)
        card_ids_to_invalidate = set()
        if "card_id" in vals or "state" in vals:
            card_ids_to_invalidate.update(self.card_id.ids)
            if vals.get("card_id"):
                card_ids_to_invalidate.add(vals["card_id"])
        result = super().write(vals)
        if card_ids_to_invalidate:
            self.env["spa.treatment.card"].browse(card_ids_to_invalidate).invalidate_recordset(
                ["reserved_by_bookings", "available_for_booking"]
            )
        return result

    def unlink(self):
        card_ids = self.card_id.ids
        result = super().unlink()
        if card_ids:
            self.env["spa.treatment.card"].browse(card_ids).invalidate_recordset(
                ["reserved_by_bookings", "available_for_booking"]
            )
        return result

    def action_confirm(self):
        self.write({"state": "confirmed"})

    def action_doing(self):
        self.write({"state": "doing"})

    def action_open_recurring_booking_wizard(self):
        """Mở wizard đặt lịch theo ngày trong tuần ngay từ form đặt lịch."""
        self.ensure_one()
        ctx = dict(self.env.context)
        if self.partner_id:
            ctx["default_partner_id"] = self.partner_id.id
        if self.card_id:
            ctx["default_card_id"] = self.card_id.id
        if self.start_datetime:
            dt = fields.Datetime.to_datetime(self.start_datetime)
            ctx["default_start_date"] = dt.date()
            ctx["default_start_time_float"] = dt.hour + (dt.minute / 60.0)
        return {
            "type": "ir.actions.act_window",
            "name": _("Đặt lịch theo ngày trong tuần"),
            "res_model": "spa.recurring.booking.wizard",
            "view_mode": "form",
            "target": "new",
            "context": ctx,
        }

    def action_open_shift_config_wizard(self):
        shift_date = self.env.context.get("shift_date") or fields.Date.context_today(self)
        if isinstance(shift_date, str):
            shift_date = fields.Date.from_string(shift_date)
        return self.env["booking.shift.config"].action_open_config_modal(shift_date)

    def action_done(self):
        for booking in self:
            if booking.session_id:
                booking.write({"state": "done"})
                continue
            target = booking._get_completion_target()
            if not target:
                raise UserError(
                    _(
                        "Chưa cấu hình đối tượng xử lý hoàn thành. "
                        "Kiểm tra hình thức lịch và thẻ / loại hoạt động."
                    )
                )
            if not hasattr(target, "spa_complete_booking"):
                raise UserError(
                    _("Model %s chưa hỗ trợ hoàn thành đặt lịch.")
                    % (booking.completion_res_model_id.model or "?")
                )
            target.spa_complete_booking(booking)

    def action_cancel(self):
        self.write({"state": "cancel"})

    def action_draft(self):
        self.write({"state": "draft"})

    def _send_reminder_activity(self):
        """Tạo activity nhắc nhân viên: KH sắp tới lịch."""
        activity_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False) or self.env["mail.activity.type"].search([("category", "=", "default")], limit=1)
        for rec in self:
            staff_users = rec.staff_ids
            if not staff_users or rec.reminder_sent:
                continue
            start = rec.start_datetime
            if not start:
                continue
            if rec.booking_kind == "non_session" and rec.non_session_offering_id:
                service_label = rec.non_session_offering_id.display_name
            else:
                service_label = (
                    rec.product_id.display_name
                    or rec.card_id.display_name
                    or _("Thẻ trị liệu")
                )
            body = _(
                "Khách hàng <strong>%s</strong> sắp tới lịch lúc <strong>%s</strong> — %s."
            ) % (rec.partner_id.name or "", start.strftime("%d/%m/%Y %H:%M"), service_label)
            for u in staff_users:
                self.env["mail.activity"].sudo().create({
                    "res_model_id": self.env["ir.model"]._get(rec._name).id,
                    "res_id": rec.id,
                    "activity_type_id": activity_type.id if activity_type else False,
                    "user_id": u.id,
                    "summary": _("Nhắc lịch: %s - %s") % (rec.partner_id.name, service_label),
                    "note": body,
                })
            rec.sudo().write({"reminder_sent": True})

    @api.model
    def get_calendar_display_config(self):
        """Trả về min_time, max_time, pixels_per_hour cho lịch đặt (frontend gọi). Từ Cấu hình Spa."""
        ICP = self.env["ir.config_parameter"].sudo()
        min_t = ICP.get_param("spa.calendar_min_time", "05:00:00")
        max_t = ICP.get_param("spa.calendar_max_time", "22:00:00")
        try:
            px = int(ICP.get_param("spa.calendar_pixels_per_hour", "80") or "80")
            px = max(40, min(360, px))
        except (TypeError, ValueError):
            px = 80
        return {
            "min_time": min_t or "05:00:00",
            "max_time": max_t or "22:00:00",
            "pixels_per_hour": px,
        }

    @api.model
    def set_calendar_display_config(self, pixels_per_hour=None, min_time=None, max_time=None):
        """Lưu cấu hình lịch (gọi từ màn hình lịch hoặc Cấu hình)."""
        ICP = self.env["ir.config_parameter"].sudo()
        if pixels_per_hour is not None:
            px = max(40, min(360, int(pixels_per_hour)))
            ICP.set_param("spa.calendar_pixels_per_hour", str(px))
        if min_time is not None and str(min_time).strip():
            ICP.set_param("spa.calendar_min_time", str(min_time).strip())
        if max_time is not None and str(max_time).strip():
            ICP.set_param("spa.calendar_max_time", str(max_time).strip())
        return self.get_calendar_display_config()

    @api.model
    def _spa_resolve_product_id_for_staff_name_search(
        self, product_id=None, card_id=None, non_session_offering_id=None
    ):
        """Dùng cho RPC chọn NV trên form đặt lịch (từ product / thẻ / offering)."""
        try:
            if product_id:
                return int(product_id)
        except (TypeError, ValueError):
            pass
        try:
            if card_id:
                card = self.env["spa.treatment.card"].browse(int(card_id))
                if card.exists() and card.product_id:
                    return card.product_id.id
        except (TypeError, ValueError):
            pass
        try:
            if non_session_offering_id:
                off = self.env["spa.booking.non_session_offering"].browse(int(non_session_offering_id))
                if off.exists() and off.product_id:
                    return off.product_id.id
        except (TypeError, ValueError):
            pass
        return False

    @api.model
    def staff_name_search_for_booking(
        self,
        name="",
        operator="ilike",
        args=None,
        limit=100,
        product_id=None,
        card_id=None,
        non_session_offering_id=None,
        start=None,
        end=None,
        duration=None,
        booking_id=None,
        context=None,
    ):
        """
        Chỉ dùng từ widget web trên form/calendar đặt lịch: gọi name_search(res.users)
        rồi đưa NV đúng lượt luân ca lên đầu. Không sửa res.users.name_search toàn cục.
        """
        args = args or []
        try:
            limit = int(limit) if limit is not None else 100
        except (TypeError, ValueError):
            limit = 100

        Users = self.env["res.users"]
        pairs = Users.name_search(name, args, operator, limit=limit)

        pid = self._spa_resolve_product_id_for_staff_name_search(
            product_id=product_id,
            card_id=card_id,
            non_session_offering_id=non_session_offering_id,
        )
        def _parse_dt(val):
            """Parse datetime coming from web client.

            Web side may send ISO 8601 strings like '2026-03-20T09:15:00.000+07:00',
            while Odoo Datetime.to_datetime expects 'YYYY-mm-dd HH:MM:SS'.
            """
            if not val:
                return False
            # `datetime` is imported from `datetime` module at file level.
            if isinstance(val, datetime):
                return val
            if isinstance(val, str):
                try:
                    return fields.Datetime.from_string(val)
                except (TypeError, ValueError):
                    # Fallback to legacy server format.
                    try:
                        return fields.Datetime.to_datetime(val)
                    except (TypeError, ValueError):
                        return False
            return False

        start_dt = _parse_dt(start)
        end_dt = _parse_dt(end)
        if not end_dt and start_dt and duration is not None:
            try:
                dm = int(duration)
            except (TypeError, ValueError):
                dm = 0
            if dm > 0:
                end_dt = start_dt + timedelta(minutes=dm)

        bk = False
        if booking_id not in (False, None, ""):
            try:
                bk = int(booking_id)
            except (TypeError, ValueError):
                bk = False
        if not bk or bk < 0:
            bk = False

        if not pid or not start_dt or not end_dt:
            return pairs

        order_ids = self.sudo()._rotation_ordered_available_ids(
            pid, start_dt, end_dt, booking_id=bk or None
        )
        if not order_ids:
            return pairs

        id_to_name = dict(pairs)
        # Khi mở dropdown trên form đặt lịch, chỉ hiển thị nhân viên "luân ca phù hợp":
        # - có dòng ca trong booking.shift.config cho ngày (slot nằm trọn trong khung đó)
        # - còn đủ capacity %
        # Các nhân viên khác không được đưa vào luân ca => không nên xuất hiện trong danh sách chọn.
        out = []
        for uid in order_ids:
            if uid in id_to_name:
                out.append((uid, id_to_name[uid]))
        return out[:limit] if limit else out

    @api.model
    def _rotation_ordered_available_ids(self, product_id, start_datetime, end_datetime, booking_id=None):
        """
        Danh sách id nhân viên khả dụng cho slot, cùng thứ tự gợi ý luân ca:
        ít lịch đặt trong ngày hơn → ca bắt đầu sớm hơn → spa_staff_sequence. Không ghi ICP.

        get_suggested_staff_ids() vẫn ghi ICP theo người đứng đầu danh sách này (tùy chọn tích hợp).
        """
        return self._spa_rotation_ordered_staff_ids(
            product_id, start_datetime, end_datetime, booking_id=booking_id
        )

    @api.model
    def get_available_staff_ids(self, product_id, start_datetime, end_datetime, booking_id=None):
        """
        Nhân viên đủ cấp độ, có ca trong booking.shift.config cho ngày local của slot
        (hoặc ca ngày hôm trước nếu slot nằm trong khung ca qua đêm), slot nằm trọn trong khung ca,
        và còn đủ capacity % trong (start_datetime, end_datetime).
        Không dùng spa_shift_start_hour / spa_shift_duration_hours trên res.users.
        booking_id: loại trừ đặt lịch này khi tính capacity (khi sửa).
        """
        if not start_datetime or not end_datetime:
            return self.env["res.users"]
        product = self.env["product.product"].browse(product_id) if product_id else None
        required_level = ""
        capacity_percent = 100
        if product and product.product_tmpl_id:
            pt = product.product_tmpl_id
            required_level = getattr(pt, "spa_required_staff_level", "") or ""
            capacity_percent = getattr(pt, "spa_staff_capacity_percent", None) or 100
        domain = [("share", "=", False)]
        if required_level == "expert":
            domain.append("|")
            domain.append(("spa_staff_level", "=", "expert"))
            domain.append(("spa_staff_level", "=", False))
        elif required_level == "regular":
            domain.append("|")
            domain.append(("spa_staff_level", "=", "regular"))
            domain.append(("spa_staff_level", "=", False))
        users = self.env["res.users"].search(domain, order="spa_staff_sequence, id")

        # Lọc theo khung ca trên booking.shift.config (ngày local + có thể ca từ hôm trước).
        #
        # Odoo lưu `start_datetime/end_datetime` ở UTC (khi DB trả về có thể là aware/naive).
        # Để so sánh đúng theo "giờ địa phương" của user (vd: Việt Nam UTC+7),
        # ta convert sang local time bằng `context_timestamp`, sau đó strip tzinfo
        # để tất cả giá trị so sánh đều là naive datetimes.
        local_start = fields.Datetime.context_timestamp(self, start_datetime) or start_datetime
        local_end = fields.Datetime.context_timestamp(self, end_datetime) or end_datetime
        if getattr(local_start, "tzinfo", None):
            local_start = local_start.replace(tzinfo=None)
        if getattr(local_end, "tzinfo", None):
            local_end = local_end.replace(tzinfo=None)
        start_dt_naive = local_start
        end_dt_naive = local_end

        # Ca làm theo ngày: chỉ booking.shift.config (modal "Ca làm"). duration=0 => nghỉ ngày đó.
        day = start_dt_naive.date()
        prev_day = day - timedelta(days=1)
        ShiftCfg = self.env["booking.shift.config"]
        shift_map_today = ShiftCfg.get_user_shift_map_for_date(day)
        shift_map_prev = ShiftCfg.get_user_shift_map_for_date(prev_day)

        def _get_shift_for_user_day(user, shift_day):
            if shift_day == day and user.id in shift_map_today:
                return shift_map_today[user.id]
            if shift_day == prev_day and user.id in shift_map_prev:
                return shift_map_prev[user.id]
            return None, None

        # A booking is considered doable by that staff if the whole [start, end]
        # fits within the staff's shift window (trong giờ local).
        def _within_shift(user):
            def _check_for_day(shift_day):
                st_hours, duration_hours = _get_shift_for_user_day(user, shift_day)
                if st_hours is None or duration_hours is None:
                    return False
                if duration_hours <= 0:
                    return False
                if st_hours < 0 or st_hours >= 24:
                    return False

                shift_start = datetime.combine(
                    shift_day, datetime.min.time()
                ) + timedelta(hours=st_hours)
                shift_end = shift_start + timedelta(hours=duration_hours)
                return start_dt_naive >= shift_start and end_dt_naive <= shift_end

            # Booking at early hours may belong to shift started from previous day.
            return _check_for_day(day) or _check_for_day(prev_day)

        result = []
        for user in users:
            if not _within_shift(user):
                continue
            total = self._sum_staff_capacity_in_range(
                user.id, start_datetime, end_datetime, exclude_booking_id=booking_id
            )
            if total + capacity_percent <= 100:
                result.append(user.id)
        return self.env["res.users"].browse(result)

    @api.model
    def get_suggested_staff_ids(self, product_id, start_datetime, end_datetime, booking_id=None):
        """
        Gợi ý nhân viên: lọc đủ cấp độ + còn capacity, sắp xếp như _spa_rotation_ordered_staff_ids
        (ít lịch trong ngày → ca sớm → sequence). Trả về list id (thứ tự ưu tiên).
        Ghi spa.rotation_last_user_id.<cấp_độ> = id đứng đầu (tương thích tích hợp cũ).
        """
        ordered = self._rotation_ordered_available_ids(
            product_id, start_datetime, end_datetime, booking_id
        )
        if not ordered:
            return []
        product = self.env["product.product"].browse(product_id) if product_id else None
        required_level = ""
        if product and product.product_tmpl_id:
            required_level = getattr(
                product.product_tmpl_id, "spa_required_staff_level", ""
            ) or ""
        level_key = required_level or "any"
        param_key = "spa.rotation_last_user_id.%s" % level_key
        self.env["ir.config_parameter"].sudo().set_param(param_key, str(ordered[0]))
        return ordered

    @api.model
    def _cron_send_booking_reminders(self):
        """Cron: gửi nhắc nhân viên trước X giờ (setting). Lịch bắt đầu nằm trong khoảng [now+Xh - 30ph, now+Xh + 30ph] thì gửi."""
        try:
            hours = float(self.env["ir.config_parameter"].sudo().get_param("spa.booking_reminder_hours_before", "2"))
        except (TypeError, ValueError):
            hours = 2.0
        now = fields.Datetime.now()
        # Lịch bắt đầu lúc (now + X giờ) → đúng lúc cần nhắc (X giờ trước khi bắt đầu)
        target = now + timedelta(hours=hours)
        window_start = target - timedelta(minutes=30)
        window_end = target + timedelta(minutes=30)
        domain = [
            ("state", "=", "draft"),
            ("reminder_sent", "=", False),
            ("start_datetime", ">=", window_start),
            ("start_datetime", "<=", window_end),
        ]
        bookings = self.search(domain)
        bookings._send_reminder_activity()
