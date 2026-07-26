/** @odoo-module **/

import {
    CalendarCommonPopover
} from "@web/views/calendar/calendar_common/calendar_common_popover";
import {
    useService
} from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

export class SpaBookingCalendarPopover extends CalendarCommonPopover {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.user = useService("user");
        this.isSpaStaff = false;
        this.isBookingOperator = false;
        onWillStart(async () => {
            this.isSpaStaff = await this.user.hasGroup("spa.group_spa_staff");
            this.isBookingOperator = await this.user.hasGroup(
                "spa.group_spa_booking_operator"
            );
        });
    }

    get state() {
        return this.props.record.rawRecord?.state?? "draft";
    }

    /** Full schedule buttons (confirm/cancel/edit) — Spa Staff only. */
    get canManageBooking() {
        return this.isSpaStaff;
    }

    /** Serve / complete — staff or booking operator. */
    get canServeOrComplete() {
        return this.isSpaStaff || this.isBookingOperator;
    }

    get hasFooter() {
        if (this.canManageBooking) {
            return (
                this.isEventEditable ||
                this.isEventDeletable ||
                this.state === "draft" ||
                this.state === "confirmed" ||
                this.state === "doing"
            );
        }
        if (this.canServeOrComplete) {
            return this.state === "confirmed" || this.state === "doing" || this.state === "draft";
        }
        return false;
    }

    /** Thứ tự hiển thị field trong body popover: trạng thái → KH → Thẻ → buổi → NV → Giường, sau đó Thời gian ở cuối. */
    get orderedPopoverFieldIds() {
        return [
            "state",
            "booking_kind",
            "partner_id",
            "non_session_offering_id",
            "card_id",
            "card_total_sessions",
            "card_available_for_booking",
            "staff_ids",
            "bed_id",
        ];
    }

    async onActionConfirm() {
        await this.orm.call("spa.service.booking", "action_confirm", [
            [this.props.record.id]
        ]);
        this.props.refreshCalendar?.();
        this.props.close();
    }

    async onActionDoing() {
        await this.orm.call("spa.service.booking", "action_doing", [
            [this.props.record.id]
        ]);
        this.props.refreshCalendar?.();
        this.props.close();
    }

    async onActionCancel() {
        await this.orm.call("spa.service.booking", "action_cancel", [
            [this.props.record.id]
        ]);
        this.props.refreshCalendar?.();
        this.props.close();
    }

    async onActionDone() {
        await this.orm.call("spa.service.booking", "action_done", [
            [this.props.record.id]
        ]);
        this.props.refreshCalendar?.();
        this.props.close();
    }
}
SpaBookingCalendarPopover.template = "web.CalendarCommonPopover";
SpaBookingCalendarPopover.subTemplates = {
    ...CalendarCommonPopover.subTemplates,
    body: "spa.SpaBookingCalendarPopover.body",
    footer: "spa.SpaBookingCalendarPopover.footer",
};
SpaBookingCalendarPopover.props = {
    ...CalendarCommonPopover.props,
    refreshCalendar: {
        type: Function,
        optional: true
    },
};
