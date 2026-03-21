/** @odoo-module **/

import {
    CalendarCommonPopover
} from "@web/views/calendar/calendar_common/calendar_common_popover";
import {
    useService
} from "@web/core/utils/hooks";

export class SpaBookingCalendarPopover extends CalendarCommonPopover {
    setup() {
        super.setup();
        this.orm = useService("orm");
    }

    get state() {
        return this.props.record.rawRecord?.state?? "draft";
    }

    get hasFooter() {
        return (
            this.isEventEditable ||
            this.isEventDeletable ||
            this.state === "draft" ||
            this.state === "confirmed" ||
            this.state === "doing"
        );
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
