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
    # Màu trên calendar: theo trạng thái (cấu hình trong Cấu hình Spa)
    state_calendar_color = fields.Integer(
        string="Màu lịch (theo trạng thái)",
        compute="_compute_state_calendar_color",
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

    def _spa_is_shift_fully_configured(self, user):
        """Chỉ coi NV tham gia luân ca nếu đủ 2 trường ca (start + duration)."""
        h = getattr(user, "spa_shift_start_hour", None)
        d = getattr(user, "spa_shift_duration_hours", None)
        if h is False or h is None:
            return False
        if d is False or d is None:
            return False
        try:
            d = float(d)
        except (TypeError, ValueError):
            return False
        if d <= 0:
            return False
        try:
            hi = int(h)
        except (TypeError, ValueError):
            return False
        # allow 0..23
        return 0 <= hi <= 23

    def _spa_staff_rotation_base_ids(self, required_level):
        """Danh sách NV đủ cấu hình ca theo cấp độ, theo thứ tự sequence."""
        domain = [("share", "=", False)]
        if required_level == "expert":
            # Cho phép cả nhân viên có spa_staff_level = NULL/False
            # để không loại hết các NV chỉ đã cấu hình giờ ca.
            domain.append("|")
            domain.append(("spa_staff_level", "=", "expert"))
            domain.append(("spa_staff_level", "=", False))
        elif required_level == "regular":
            # "regular": chỉ nhân viên (loại bỏ chuyên gia).
            # Vẫn cho phép NULL/False để không loại hết NV đã cấu hình giờ ca,
            # nhưng không bao giờ đưa NV 'expert' vào nhóm regular.
            domain.append("|")
            domain.append(("spa_staff_level", "=", "regular"))
            domain.append(("spa_staff_level", "=", False))

        users = self.env["res.users"].search(domain, order="spa_staff_sequence,id")
        filtered = users.filtered(lambda u: self._spa_is_shift_fully_configured(u))
        return filtered.ids

    def _spa_rotation_ordered_staff_ids_by_history(self, product_id, start_dt, end_dt, booking_id=None):
        """
        Đặt thứ tự gợi ý theo luân ca dựa trên "NV mới nhất đã làm trước thời điểm này"
        trong cùng nhóm cấp độ (expert/regular/any), sau đó lấy các NV đang rảnh để hiển thị.
        """
        if not product_id or not start_dt or not end_dt:
            return []

        # 1) NV đang rảnh cho slot hiện tại
        available = self.get_available_staff_ids(product_id, start_dt, end_dt, booking_id=booking_id)
        if not available:
            return []

        # 2) Xác định cấp độ yêu cầu từ product template
        product = self.env["product.product"].browse(product_id)
        required_level = ""
        if product and product.product_tmpl_id:
            required_level = getattr(product.product_tmpl_id, "spa_required_staff_level", "") or ""

        level_key = required_level or "any"
        # 3) Base rotation list: tất cả NV đủ cấu hình ca trong nhóm cấp độ
        base_ids = self._spa_staff_rotation_base_ids(level_key)
        if not base_ids:
            return available.ids

        available_set = set(available.ids)

        # 4) Tìm NV đã làm gần nhất trước thời điểm start_dt (trong base_ids)
        #
        # Reset theo "ngày mới": nếu booking gần nhất rơi vào ngày khác
        # thì bỏ qua để thứ tự ưu tiên của lần đầu trong ngày bắt đầu lại theo spa_staff_sequence.
        # Reset theo "ngày mới" dựa trên local day (timezone của user).
        local_start = fields.Datetime.context_timestamp(self, start_dt) or start_dt
        if getattr(local_start, "tzinfo", None):
            local_start = local_start.replace(tzinfo=None)
        start_day_naive = local_start.date()
        Booking = self.env["spa.service.booking"]
        dom = [
            # Rotation dựa trên lịch sử "thực" (loại trừ draft/cancel),
            # để lần đầu trong ngày không bị xoay do các draft thử nghiệm trước đó.
            ("state", "not in", ["cancel", "draft"]),
            ("start_datetime", "<", start_dt),
            ("staff_ids", "in", base_ids),
        ]
        if booking_id:
            dom.append(("id", "!=", booking_id))
        last_booking = Booking.search(dom, order="start_datetime desc, id desc", limit=1)
        if last_booking and last_booking.staff_ids:
            local_last_start = (
                fields.Datetime.context_timestamp(self, last_booking.start_datetime)
                or last_booking.start_datetime
            )
            if getattr(local_last_start, "tzinfo", None):
                local_last_start = local_last_start.replace(tzinfo=None)
            last_day_naive = local_last_start.date()
            if last_day_naive != start_day_naive:
                last_id = False
            else:
                last_staff = sorted(
                    last_booking.staff_ids, key=lambda u: (u.spa_staff_sequence or 0, u.id)
                )[0]
                last_id = last_staff.id
        else:
            last_id = False

        # 5) Luân ca: bắt đầu sau last_id trong base_ids
        if last_id in base_ids:
            idx = base_ids.index(last_id)
            rotated = base_ids[idx + 1 :] + base_ids[: idx + 1]
        else:
            rotated = base_ids

        # 6) Chỉ lấy phần tử đang rảnh
        ordered_available = [uid for uid in rotated if uid in available_set]
        # Fallback: nếu vòng quay lọc hết, dùng available hiện tại
        return ordered_available or available.ids

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
        "staff_ids",
        "staff_ids.name",
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

            # Line 1: Mã KH - Tên KH
            customer_line = ""
            if rec.partner_id:
                customer_line = _join_code_name(
                    rec.partner_id.customer_code,
                    rec.partner_id.name or rec.partner_id.display_name,
                )

            # Line 3: Tên nhân viên
            staff_line = ""
            staff_users = rec.staff_ids
            if staff_users:
                if isinstance(staff_users, models.BaseModel):
                    # recordset (many2many) or single (many2one)
                    names = staff_users.mapped("name")
                else:
                    names = []
                staff_line = ", ".join([n for n in names if n]) if names else ""

            # Line 2: Mã dịch vụ - Tên dịch vụ
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

            # Render cố định 3 dòng: KH, Dịch vụ, Nhân viên
            rec.calendar_event_title = "\n".join(
                [
                    customer_line or "",
                    service_line or "",
                    staff_line or "",
                ]
            )

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

    def _get_calendar_color_index_for_state(self, state):
        """Chỉ số màu (0–55) cho trạng thái, đọc từ Cấu hình Spa."""
        ICP = self.env["ir.config_parameter"].sudo()
        key = "spa.booking_calendar_color_%s" % (state or "draft")
        default = {"draft": 1, "confirmed": 2, "doing": 3, "done": 4, "cancel": 0}.get(
            state, 0
        )
        try:
            return max(0, min(55, int(ICP.get_param(key, str(default)))))
        except (TypeError, ValueError):
            return default

    @api.depends("state")
    def _compute_state_calendar_color(self):
        for rec in self:
            rec.state_calendar_color = rec._get_calendar_color_index_for_state(rec.state)

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
        # - có đủ 2 trường ca
        # - slot nằm trọn trong khung ca
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
        Danh sách id nhân viên khả dụng cho slot, đã xoay vòng theo ir.config_parameter
        (spa.rotation_last_user_id.<cấp_độ>). Không ghi ICP — dùng cho dropdown chọn NV.

        Logic luân ca đầy đủ (kèm ghi nhận lượt) nằm ở get_suggested_staff_ids().
        """
        available = self.get_available_staff_ids(product_id, start_datetime, end_datetime, booking_id)
        if not available:
            return []
        product = self.env["product.product"].browse(product_id) if product_id else None
        required_level = ""
        if product and product.product_tmpl_id:
            required_level = getattr(
                product.product_tmpl_id, "spa_required_staff_level", ""
            ) or ""
        level_key = required_level or "any"
        ICP = self.env["ir.config_parameter"].sudo()
        param_key = "spa.rotation_last_user_id.%s" % level_key
        last_id = False
        try:
            last_id = int(ICP.get_param(param_key, "0") or "0")
        except (TypeError, ValueError):
            pass
        ids = list(available.ids)
        if not ids:
            return []
        if last_id in ids:
            idx = ids.index(last_id)
            return ids[idx + 1 :] + ids[: idx + 1]
        return ids

    @api.model
    def get_available_staff_ids(self, product_id, start_datetime, end_datetime, booking_id=None):
        """
        Nhân viên đủ cấp độ, đã khai báo đủ giờ bắt đầu ca + thời lượng ca (Spa),
        slot nằm trọn trong ca, và còn đủ capacity % trong (start_datetime, end_datetime).
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
        # Luân ca / gợi ý: chỉ NV đã khai báo đủ giờ bắt đầu ca + thời lượng (> 0).
        def _shift_fully_configured(user):
            h = user.spa_shift_start_hour
            if h is False or h is None:
                return False
            d = user.spa_shift_duration_hours
            if d is False or d is None:
                return False
            try:
                d = float(d)
            except (TypeError, ValueError):
                return False
            if d <= 0:
                return False
            try:
                hi = int(h)
            except (TypeError, ValueError):
                return False
            if hi < 0 or hi > 23:
                return False
            return True

        # Filter by shift window (ca bắt đầu + duration_hours).
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

        # A booking is considered doable by that staff if the whole [start, end]
        # fits within the staff's shift window (trong giờ local).
        def _within_shift(user):
            if not _shift_fully_configured(user):
                return False
            shift_start_hour = int(user.spa_shift_start_hour)
            duration_hours = float(user.spa_shift_duration_hours)

            day = start_dt_naive.date()
            prev_day = day - timedelta(days=1)

            def _check_for_day(d):
                shift_start = datetime.combine(d, datetime.min.time()).replace(
                    hour=shift_start_hour, minute=0, second=0, microsecond=0
                )
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
        Gợi ý nhân viên theo luân chuyển: lọc đủ cấp độ + còn capacity, sắp xếp theo vòng luân chuyển,
        người đúng lượt nếu bận thì bỏ qua và gợi ý người tiếp theo còn rảnh.
        Trả về list id (thứ tự ưu tiên). Mỗi lần gọi sẽ ghi lại con trỏ luân ca (ICP).

        Thứ tự hiển thị trên form (không ghi ICP) dùng _rotation_ordered_available_ids + name_search res.users.
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
