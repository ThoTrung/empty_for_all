# -*- coding: utf-8 -*-

from datetime import datetime, timedelta

from odoo.tests import TransactionCase
from odoo.exceptions import ValidationError, UserError


class TestBookingCalendar(TransactionCase):
    """Test đặt lịch: recurring, capacity %, composite, gợi ý nhân viên."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, tracking_disable=True))
        # Partner
        cls.partner = cls.env["res.partner"].create({
            "name": "Customer Test Booking",
            "is_company": False,
        })
        # Users (staff)
        cls.user_a = cls.env.ref("base.user_admin")
        cls.user_a.spa_staff_level = "expert"
        cls.user_b = cls.env["res.users"].create({
            "name": "Staff B",
            "login": "staff_b_booking_test",
            "spa_staff_level": "regular",
        })

        # Staff rotation by shift start hour
        cls.user_shift9 = cls.env["res.users"].create({
            "name": "Staff Shift 9",
            "login": "staff_shift_9_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 9,
            "spa_shift_duration_hours": 10.0,
        })
        cls.user_shift10 = cls.env["res.users"].create({
            "name": "Staff Shift 10",
            "login": "staff_shift_10_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 10,
            "spa_shift_duration_hours": 10.0,
        })
        # base.user_admin is the primary expert staff in the existing tests
        cls.user_a.spa_shift_start_hour = 8
        cls.user_a.spa_shift_duration_hours = 10.0
        # Prevent other expert users from affecting shift-based tests.
        other_expert_staff = cls.env["res.users"].search([
            ("share", "=", False),
            ("spa_staff_level", "=", "expert"),
        ])
        for u in other_expert_staff:
            if u.id not in (cls.user_a.id, cls.user_shift9.id, cls.user_shift10.id):
                u.spa_shift_start_hour = 16
                u.spa_shift_duration_hours = 10.0

        # Test DB có thể có nhân viên có giờ ca nhưng spa_staff_level đang để trống (NULL/False).
        # Vì ta cho phép NULL/False tham gia luân ca, cần đẩy chúng ra khỏi khung giờ test.
        other_null_level_shift_staff = cls.env["res.users"].search([
            ("share", "=", False),
            ("spa_staff_level", "=", False),
            ("spa_shift_start_hour", "!=", False),
            ("spa_shift_duration_hours", "!=", False),
        ])
        for u in other_null_level_shift_staff:
            u.spa_shift_start_hour = 16
            u.spa_shift_duration_hours = 10.0
        # Product service (simple) - tạo qua template
        def make_service(name, sessions=1, duration=60, capacity=100, level=False):
            tmpl = cls.env["product.template"].create({
                "name": name,
                "detailed_type": "service",
                "list_price": 100,
                "spa_sessions_per_unit": sessions,
                "spa_duration_minutes": duration,
                "spa_staff_capacity_percent": capacity,
                "spa_required_staff_level": level,
            })
            return tmpl.product_variant_id

        cls.product_svc = make_service("Service 60min", sessions=5, duration=60, capacity=100, level=False)
        cls.product_20 = make_service("Service 20%", sessions=1, duration=30, capacity=20, level="regular")
        cls.product_90 = make_service("Service 90%", sessions=1, duration=60, capacity=90, level="expert")
        # Services only consuming 20% / 30% of staff capacity (expert-only for deterministic tests)
        cls.product_20_expert = make_service(
            "Service 20% expert",
            sessions=1,
            duration=30,
            capacity=20,
            level="expert",
        )
        cls.product_30_expert = make_service(
            "Service 30% expert",
            sessions=1,
            duration=30,
            capacity=30,
            level="expert",
        )
        cls.product_20.list_price = 50
        cls.product_90.list_price = 80
        # Bed
        cls.bed = cls.env["spa.bed"].create({"name": "Bed 1"})
        # Treatment card
        cls.card = cls.env["spa.treatment.card"].create({
            "name": "Card Test",
            "partner_id": cls.partner.id,
            "product_id": cls.product_svc.id,
            "total_sessions": 10,
            "duration_minutes": 60,
        })

    def test_booking_simple_unchanged(self):
        """Đặt lịch đơn giản (1 NV, 1 giường) vẫn hoạt động như cũ."""
        start = datetime.now() + timedelta(days=1)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        booking = self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "product_id": self.product_svc.id,
            "start_datetime": start,
            "duration": 60,
            "staff_ids": [(6, 0, [self.user_a.id])],
            "bed_id": self.bed.id,
        })
        self.assertTrue(booking.name)
        self.assertEqual(booking.state, "draft")
        self.assertIn(self.user_a, booking.staff_ids)
        self.assertEqual(booking.bed_id, self.bed)

    def test_booking_recurring_without_staff_bed(self):
        """Đặt lịch theo chuỗi: có thể tạo không có staff_id và bed_id."""
        start = datetime.now() + timedelta(days=1)
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)
        booking = self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "product_id": self.product_svc.id,
            "start_datetime": start,
            "duration": 60,
            "bed_id": False,
        })
        self.assertTrue(booking.id)
        self.assertFalse(booking.staff_ids)
        self.assertFalse(booking.bed_id)

    def test_recurring_wizard_creates_bookings(self):
        """Wizard đặt lịch theo ngày trong tuần tạo đủ số buổi."""
        self.card.booking_ids.unlink()
        wizard = self.env["spa.recurring.booking.wizard"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "start_date": self.env.context.get("date") or datetime.now().date(),
            "start_time_float": 9.0,
            "mon": True,
            "fri": True,
        })
        count_before = self.env["spa.service.booking"].search_count([
            ("card_id", "=", self.card.id),
        ])
        action = wizard.action_create_bookings()
        count_after = self.env["spa.service.booking"].search_count([
            ("card_id", "=", self.card.id),
        ])
        self.assertGreater(count_after, count_before)
        self.assertIn("domain", action)
        self.assertIsInstance(action.get("domain"), list)

    def test_recurring_wizard_needs_weekdays(self):
        """Wizard báo lỗi nếu không chọn ngày nào trong tuần."""
        wizard = self.env["spa.recurring.booking.wizard"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "start_date": datetime.now().date(),
            "start_time_float": 9.0,
            "mon": False,
            "tue": False,
            "wed": False,
            "thu": False,
            "fri": False,
            "sat": False,
            "sun": False,
        })
        with self.assertRaises(UserError):
            wizard.action_create_bookings()

    def test_capacity_allow_multiple_same_slot(self):
        """Cùng 1 nhân viên: 20% + 30% trong cùng khung giờ được phép (≤100%)."""
        start = datetime.now() + timedelta(days=2)
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)
        self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "product_id": self.product_20.id,
            "start_datetime": start,
            "duration": 60,
            "staff_ids": [(6, 0, [self.user_a.id])],
            "bed_id": self.bed.id,
        })
        card2 = self.env["spa.treatment.card"].create({
            "name": "Card 2",
            "partner_id": self.partner.id,
            "product_id": self.product_20.id,
            "total_sessions": 1,
            "duration_minutes": 30,
        })
        tmpl_30 = self.env["product.template"].create({
            "name": "Service 30%",
            "detailed_type": "service",
            "list_price": 40,
            "spa_sessions_per_unit": 1,
            "spa_duration_minutes": 30,
            "spa_staff_capacity_percent": 30,
        })
        product_30 = tmpl_30.product_variant_id
        booking2 = self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": card2.id,
            "product_id": product_30.id,
            "start_datetime": start,
            "duration": 30,
            "staff_ids": [(6, 0, [self.user_a.id])],
            "bed_id": self.bed.id,
        })
        self.assertTrue(booking2.id)

    def test_capacity_allow_multiple_same_slot_when_product_id_missing(self):
        """Booking kiểu card mà `product_id` NULL vẫn phải tính capacity % theo card.product_id."""
        booking_model = self.env["spa.service.booking"]

        card_20 = self.env["spa.treatment.card"].create({
            "name": "Card 20% Expert (for cap missing product_id)",
            "partner_id": self.partner.id,
            "product_id": self.product_20_expert.id,
            "total_sessions": 10,
            "duration_minutes": 60,
        })

        start = datetime.now() + timedelta(days=20)
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)

        booking1 = booking_model.create({
            "partner_id": self.partner.id,
            "card_id": card_20.id,
            "booking_kind": "card",
            "start_datetime": start,
            "duration": 60,
            "staff_ids": [(6, 0, [self.user_a.id])],
            "bed_id": self.bed.id,
            "state": "draft",
        })
        self.assertTrue(booking1.id)

        # 20% + 20% = 40% <= 100 => phải cho phép tạo thêm cùng slot
        booking2 = booking_model.create({
            "partner_id": self.partner.id,
            "card_id": card_20.id,
            "booking_kind": "card",
            "start_datetime": start,
            "duration": 60,
            "staff_ids": [(6, 0, [self.user_a.id])],
            "bed_id": self.bed.id,
            "state": "draft",
        })
        self.assertTrue(booking2.id)

    def test_capacity_reject_over_100(self):
        """Cùng 1 nhân viên: đã có 20%, thêm 90% trong cùng khung giờ → ValidationError."""
        start = datetime.now() + timedelta(days=3)
        start = start.replace(hour=14, minute=0, second=0, microsecond=0)
        self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": self.card.id,
            "product_id": self.product_20.id,
            "start_datetime": start,
            "duration": 60,
            "staff_ids": [(6, 0, [self.user_a.id])],
            "bed_id": self.bed.id,
        })
        card2 = self.env["spa.treatment.card"].create({
            "name": "Card Over",
            "partner_id": self.partner.id,
            "product_id": self.product_90.id,
            "total_sessions": 1,
            "duration_minutes": 60,
        })
        with self.assertRaises(ValidationError):
            self.env["spa.service.booking"].create({
                "partner_id": self.partner.id,
                "card_id": card2.id,
                "product_id": self.product_90.id,
                "start_datetime": start,
                "duration": 60,
                "staff_ids": [(6, 0, [self.user_a.id])],
                "bed_id": self.bed.id,
            })

    def test_capacity_reject_multi_staff_over_100(self):
        """Nhiều nhân viên cùng 1 booking: từng nhân viên đều bị tính capacity và bị chặn nếu vượt 100%."""
        start = datetime.now() + timedelta(days=6)
        start = start.replace(hour=15, minute=0, second=0, microsecond=0)
        # Booking 90% cho cả A và B cùng lúc
        card90 = self.env["spa.treatment.card"].create({
            "name": "Card 90",
            "partner_id": self.partner.id,
            "product_id": self.product_90.id,
            "total_sessions": 1,
            "duration_minutes": 60,
        })
        self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": card90.id,
            "product_id": self.product_90.id,
            "start_datetime": start,
            "duration": 60,
            "staff_ids": [(6, 0, [self.user_a.id, self.user_b.id])],
            "bed_id": self.bed.id,
        })
        # Thêm booking 20% cho staff B cùng khung giờ -> 90 + 20 > 100 => lỗi
        card20 = self.env["spa.treatment.card"].create({
            "name": "Card 20",
            "partner_id": self.partner.id,
            "product_id": self.product_20.id,
            "total_sessions": 1,
            "duration_minutes": 30,
        })
        with self.assertRaises(ValidationError):
            self.env["spa.service.booking"].create({
                "partner_id": self.partner.id,
                "card_id": card20.id,
                "product_id": self.product_20.id,
                "start_datetime": start,
                "duration": 30,
                    "staff_ids": [(6, 0, [self.user_b.id])],
                "bed_id": self.bed.id,
            })

    def test_get_available_staff_ids(self):
        """get_available_staff_ids lọc NV đủ cấp độ, có đủ cấu hình ca và còn capacity."""
        start = datetime.now() + timedelta(days=4)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=60)
        ids = self.env["spa.service.booking"].get_available_staff_ids(
            self.product_svc.id, start, end
        )
        self.assertIn(self.user_a.id, ids.ids)
        # NV không khai báo đủ giờ bắt đầu + thời lượng ca không tham gia luân ca / gợi ý.
        self.assertNotIn(self.user_b.id, ids.ids)

    def test_get_suggested_staff_ids_returns_list(self):
        """get_suggested_staff_ids trả về list id theo thứ tự ưu tiên."""
        start = datetime.now() + timedelta(days=5)
        start = start.replace(hour=11, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=60)
        ids = self.env["spa.service.booking"].get_suggested_staff_ids(
            self.product_svc.id, start, end
        )
        self.assertIsInstance(ids, list)
        self.assertTrue(all(isinstance(i, int) for i in ids))

    def test_shift_filter_available_staff_ids(self):
        """Gợi ý chỉ bao gồm NV có ca chứa toàn bộ slot đặt lịch."""
        start = datetime.now() + timedelta(days=7)
        start = start.replace(hour=8, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        avail = self.env["spa.service.booking"].get_available_staff_ids(
            self.product_20_expert.id, start, end
        )
        avail_ids = set(avail.ids)
        self.assertEqual(avail_ids, {self.user_a.id})
        self.assertNotIn(self.user_shift9.id, avail_ids)
        self.assertNotIn(self.user_shift10.id, avail_ids)

    def test_regular_service_excludes_expert(self):
        """Dịch vụ cấp độ 'nhân viên' chỉ gợi ý NV (regular), không gợi ý chuyên gia (expert)."""
        booking_model = self.env["spa.service.booking"]

        # Slot nằm trong khung ca start_hour=8, duration_hours=10
        start = datetime.now() + timedelta(days=12)
        start = start.replace(hour=9, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        regular_staff = self.env["res.users"].create({
            "name": "Regular Suggestion",
            "login": "regular_suggestion_booking_test",
            "spa_staff_level": "regular",
            "spa_shift_start_hour": 8,
            "spa_shift_duration_hours": 10.0,
            "spa_staff_sequence": 1,
        })
        expert_staff = self.env["res.users"].create({
            "name": "Expert Should Not Appear",
            "login": "expert_should_not_appear_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 8,
            "spa_shift_duration_hours": 10.0,
            "spa_staff_sequence": 2,
        })

        avail_ids = set(booking_model.get_available_staff_ids(
            self.product_20.id, start, end
        ).ids)
        self.assertIn(regular_staff.id, avail_ids)
        self.assertNotIn(expert_staff.id, avail_ids)

        ordered_ids = booking_model._spa_rotation_ordered_staff_ids_by_history(
            product_id=self.product_20.id,
            start_dt=start,
            end_dt=end,
            booking_id=False,
        )
        self.assertTrue(ordered_ids)
        self.assertEqual(ordered_ids[0], regular_staff.id)

    def test_suggested_staff_rotation_by_history_next_after_busy(self):
        """Gợi ý luân ca theo history: người vừa bận thì không được đứng đầu."""
        # Tắt NV expert sẵn có trong setup để tránh nhiễu.
        for u in (self.user_a, self.user_shift9, self.user_shift10):
            u.spa_shift_start_hour = False
            u.spa_shift_duration_hours = False

        # Base order A,B,C,D theo sequence
        staff_a = self.env["res.users"].create({
            "name": "Hist Staff A",
            "login": "hist_staff_a_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 8,
            "spa_shift_duration_hours": 2.0,
            "spa_staff_sequence": 1,
        })
        staff_b = self.env["res.users"].create({
            "name": "Hist Staff B",
            "login": "hist_staff_b_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 8,
            "spa_shift_duration_hours": 2.0,
            "spa_staff_sequence": 2,
        })
        staff_c = self.env["res.users"].create({
            "name": "Hist Staff C",
            "login": "hist_staff_c_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 8,
            "spa_shift_duration_hours": 2.0,
            "spa_staff_sequence": 3,
        })
        staff_d = self.env["res.users"].create({
            "name": "Hist Staff D",
            "login": "hist_staff_d_booking_test",
            "spa_staff_level": "expert",
            "spa_shift_start_hour": 8,
            "spa_shift_duration_hours": 2.0,
            "spa_staff_sequence": 4,
        })

        base_day = datetime.now() + timedelta(days=40)
        start_prev = base_day.replace(hour=8, minute=0, second=0, microsecond=0)
        end_prev = start_prev + timedelta(minutes=60)
        start_now = base_day.replace(hour=8, minute=15, second=0, microsecond=0)
        end_now = start_now + timedelta(minutes=30)

        # Booking trước: dùng product capacity 90 để làm cho A "bận" với current slot (20%).
        card_prev = self.env["spa.treatment.card"].create({
            "name": "Hist Card Prev 90",
            "partner_id": self.partner.id,
            "product_id": self.product_90.id,
            "total_sessions": 10,
            "duration_minutes": 60,
        })
        self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": card_prev.id,
            "product_id": self.product_90.id,
            "booking_kind": "card",
            "start_datetime": start_prev,
            "duration": 60,
            "staff_ids": [(6, 0, [staff_a.id])],
            "bed_id": False,
            "state": "confirmed",
        })

        card_now = self.env["spa.treatment.card"].create({
            "name": "Hist Card Now 20 Expert",
            "partner_id": self.partner.id,
            "product_id": self.product_20_expert.id,
            "total_sessions": 10,
            "duration_minutes": 30,
        })
        current_booking = self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "card_id": card_now.id,
            "product_id": self.product_20_expert.id,
            "booking_kind": "card",
            "start_datetime": start_now,
            "duration": 30,
            "staff_ids": False,
            "bed_id": False,
            "state": "draft",
        })

        ordered_ids = current_booking._spa_rotation_ordered_staff_ids_by_history(
            product_id=self.product_20_expert.id,
            start_dt=start_now,
            end_dt=end_now,
            booking_id=current_booking.id,
        )
        self.assertTrue(ordered_ids)
        self.assertEqual(ordered_ids[0], staff_b.id)

    def test_rotation_round_robin_with_shifts(self):
        """Luân ca: vòng theo thứ tự ids trong available list."""
        start = datetime.now() + timedelta(days=8)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        booking_model = self.env["spa.service.booking"]
        avail_ids = booking_model.get_available_staff_ids(
            self.product_20_expert.id, start, end
        ).ids
        self.assertEqual(set(avail_ids), {self.user_a.id, self.user_shift9.id, self.user_shift10.id})

        ICP = self.env["ir.config_parameter"].sudo()
        param_key = "spa.rotation_last_user_id.expert"
        last_id = avail_ids[0]
        ICP.set_param(param_key, str(last_id))

        order1 = booking_model.get_suggested_staff_ids(self.product_20_expert.id, start, end)
        self.assertEqual(order1, avail_ids[1:] + avail_ids[:1])
        self.assertEqual(order1[0], avail_ids[1])

        order2 = booking_model.get_suggested_staff_ids(self.product_20_expert.id, start, end)
        self.assertEqual(order2, avail_ids[2:] + avail_ids[:2])
        self.assertEqual(order2[0], avail_ids[2])

        order3 = booking_model.get_suggested_staff_ids(self.product_20_expert.id, start, end)
        self.assertEqual(order3, avail_ids[:1] + avail_ids[1:2] + avail_ids[2:])  # wrap
        self.assertEqual(order3[0], avail_ids[0])

    def test_capacity_filter_20_30_with_shift_and_rotation(self):
        """Capacity % 20/30%: NV đã đầy capacity thì không được gợi ý."""
        start = datetime.now() + timedelta(days=9)
        start = start.replace(hour=10, minute=0, second=0, microsecond=0)
        end = start + timedelta(minutes=30)

        # Occupy 90% capacity (3 x 30%) on shift8 staff (self.user_a)
        card30exp = self.env["spa.treatment.card"].create({
            "name": "Card 30% expert",
            "partner_id": self.partner.id,
            "product_id": self.product_30_expert.id,
            "total_sessions": 10,
            "duration_minutes": 30,
        })
        for _i in range(3):
            self.env["spa.service.booking"].create({
                "partner_id": self.partner.id,
                "card_id": card30exp.id,
                "product_id": self.product_30_expert.id,
                "start_datetime": start,
                "duration": 30,
                "staff_ids": [(6, 0, [self.user_a.id])],
                "bed_id": False,
            })

        booking_model = self.env["spa.service.booking"]
        avail_ids = booking_model.get_available_staff_ids(
            self.product_20_expert.id, start, end
        ).ids
        self.assertEqual(set(avail_ids), {self.user_shift9.id, self.user_shift10.id})

        # Rotation among the remaining 2 staff
        ICP = self.env["ir.config_parameter"].sudo()
        param_key = "spa.rotation_last_user_id.expert"
        ICP.set_param(param_key, str(avail_ids[0]))

        order1 = booking_model.get_suggested_staff_ids(self.product_20_expert.id, start, end)
        self.assertEqual(order1[0], avail_ids[1])
        order2 = booking_model.get_suggested_staff_ids(self.product_20_expert.id, start, end)
        self.assertEqual(order2[0], avail_ids[0])

    def test_product_sub_service_and_composite(self):
        """Dịch vụ cha có dịch vụ con, thứ tự sequence."""
        parent_tmpl = self.env["product.template"].create({
            "name": "Composite Service",
            "detailed_type": "service",
            "list_price": 200,
            "spa_sessions_per_unit": 1,
            "spa_duration_minutes": 90,
        })
        parent = parent_tmpl
        child1 = self.product_20.product_tmpl_id
        child2 = self.product_90.product_tmpl_id
        self.env["spa.product.sub.service"].create([
            {"product_tmpl_id": parent.id, "sub_product_tmpl_id": child1.id, "sequence": 1, "duration_minutes": 30},
            {"product_tmpl_id": parent.id, "sub_product_tmpl_id": child2.id, "sequence": 2, "duration_minutes": 60},
        ])
        self.assertTrue(parent.is_composite_service)
        self.assertEqual(len(parent.spa_sub_service_ids), 2)

    def test_non_session_booking_action_done(self):
        """Hình thức không trừ buổi: Hoàn thành tạo session không gắn thẻ."""
        off = self.env["spa.booking.non_session_offering"].create({
            "name": "Test internal",
            "duration_minutes": 30,
        })
        start = datetime.now() + timedelta(days=2)
        start = start.replace(hour=14, minute=0, second=0, microsecond=0)
        booking = self.env["spa.service.booking"].create({
            "partner_id": self.partner.id,
            "booking_kind": "non_session",
            "non_session_offering_id": off.id,
            "start_datetime": start,
            "duration": 30,
            "staff_ids": [(6, 0, [self.user_a.id])],
        })
        booking.action_confirm()
        booking.action_doing()
        booking.action_done()
        self.assertEqual(booking.state, "done")
        self.assertTrue(booking.session_id)
        self.assertFalse(booking.session_id.card_id)
        self.assertEqual(booking.session_id.partner_id, self.partner)

    def test_non_session_requires_offering(self):
        with self.assertRaises(ValidationError):
            self.env["spa.service.booking"].create({
                "partner_id": self.partner.id,
                "booking_kind": "non_session",
                "start_datetime": datetime.now() + timedelta(days=1),
                "duration": 60,
            })

    def test_card_kind_requires_card(self):
        with self.assertRaises(ValidationError):
            self.env["spa.service.booking"].create({
                "partner_id": self.partner.id,
                "booking_kind": "card",
                "start_datetime": datetime.now() + timedelta(days=1),
                "duration": 60,
            })
