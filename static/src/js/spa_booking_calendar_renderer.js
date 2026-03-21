/** @odoo-module **/

import {
    CalendarCommonRenderer
} from "@web/views/calendar/calendar_common/calendar_common_renderer";
import {
    CalendarYearRenderer
} from "@web/views/calendar/calendar_year/calendar_year_renderer";
import {
    SpaBookingCalendarPopover
} from "./spa_booking_calendar_popover";
import {
    ActionSwiper
} from "@web/core/action_swiper/action_swiper";

import {
    Component
} from "@odoo/owl";

export class SpaBookingCalendarCommonRenderer extends CalendarCommonRenderer {
    getPopoverProps(record) {
        const props = super.getPopoverProps(record);
        props.refreshCalendar = () => this.props.model.load();
        return props;
    }

    // Với spa.service.booking: click vào event mở form ngay (không hiển thị popover/modal nhỏ).
    onClick(info) {
        const eventId = info?.event?.id;
        if (!eventId) {
            return;
        }
        const record = this.props.model.records[eventId];
        if (!record) {
            return;
        }
        this.props.editRecord(record);
    }
}
SpaBookingCalendarCommonRenderer.components = {
    ...CalendarCommonRenderer.components,
    Popover: SpaBookingCalendarPopover,
};

export class SpaBookingCalendarRenderer extends Component {
    get calendarComponent() {
        const scale = this.props.model?.scale;
        const comp = this.constructor.components[scale];
        return comp?? this.constructor.components.week;
    }
    get calendarKey() {
        return `${this.props.model.scale}_${this.props.model.date.valueOf()}`;
    }
    get actionSwiperProps() {
        return {
            onLeftSwipe: this.env.isSmall?{
                action: () => this.props.setDate("next")
            } : undefined,
            onRightSwipe: this.env.isSmall?{
                action: () => this.props.setDate("previous")
            } : undefined,
            animationOnMove: false,
            animationType: "forwards",
            swipeDistanceRatio: 6,
            swipeInvalid: () => Boolean(document.querySelector(".o_event.fc-mirror")),
        };
    }
}
SpaBookingCalendarRenderer.components = {
    day: SpaBookingCalendarCommonRenderer,
    week: SpaBookingCalendarCommonRenderer,
    month: SpaBookingCalendarCommonRenderer,
    year: CalendarYearRenderer,
    ActionSwiper,
};
SpaBookingCalendarRenderer.template = "web.CalendarRenderer";
