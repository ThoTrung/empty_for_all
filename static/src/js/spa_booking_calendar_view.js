/** @odoo-module **/

import {
    CalendarCommonRenderer
} from "@web/views/calendar/calendar_common/calendar_common_renderer";
import {
    CalendarController
} from "@web/views/calendar/calendar_controller";
import {
    CalendarModel
} from "@web/views/calendar/calendar_model";
import {
    SpaBookingCalendarRenderer
} from "./spa_booking_calendar_renderer";
// Cài đặt chiều cao ngay trên màn hình lịch: dùng buttonTemplate riêng + component trong controller
import {
    SpaCalendarHeightSelector
} from "./spa_calendar_height_selector";
import {
    registry
} from "@web/core/registry";

const DEFAULT_MIN_TIME = "05:00:00";
const DEFAULT_MAX_TIME = "22:00:00";
const DEFAULT_PIXELS_PER_HOUR = 80;

function parseTimeToHours(timeStr) {
    if (!timeStr || typeof timeStr !== "string") return 0;
    const parts = String(timeStr).trim().split(/[:\s]+/);
    const h = parseInt(parts[0], 10) || 0;
    const m = (parseInt(parts[1], 10) || 0) / 60;
    const s = (parseInt(parts[2], 10) || 0) / 3600;
    return h + m + s;
}

function computeContentHeight(minTime, maxTime, pixelsPerHour) {
    const hours = parseTimeToHours(maxTime) - parseTimeToHours(minTime);
    if (hours <= 0 || !pixelsPerHour) return 0;
    return 600;
    // return (Math.round(hours * pixelsPerHour) / 2 + 24 * 6);
}

// Nạp cấu hình khung giờ + độ cao từ Cấu hình Spa khi mở lịch đặt lịch
const originalLoad = CalendarModel.prototype.load;
CalendarModel.prototype.load = async function(params = {}) {
    Object.assign(this.meta, params);
    if (this.meta.resModel === "spa.service.booking") {
        try {
            const config = await this.orm.call(
                "spa.service.booking",
                "get_calendar_display_config",
                []
            );
            const minT = config.min_time || DEFAULT_MIN_TIME;
            const maxT = config.max_time || DEFAULT_MAX_TIME;
            const px = config.pixels_per_hour??DEFAULT_PIXELS_PER_HOUR;
            this.meta.spa_calendar_min_time = minT;
            this.meta.spa_calendar_max_time = maxT;
            this.meta.spa_calendar_pixels_per_hour = px;
            // this.meta.spa_calendar_content_height = computeContentHeight(
            //     minT,
            //     maxT,
            //     px
            // );
        } catch (_e) {
            this.meta.spa_calendar_min_time = DEFAULT_MIN_TIME;
            this.meta.spa_calendar_max_time = DEFAULT_MAX_TIME;
            this.meta.spa_calendar_pixels_per_hour = DEFAULT_PIXELS_PER_HOUR;
            // this.meta.spa_calendar_content_height = computeContentHeight(
            //     DEFAULT_MIN_TIME,
            //     DEFAULT_MAX_TIME,
            //     DEFAULT_PIXELS_PER_HOUR
            // );
        }
    }
    return originalLoad.call(this, params);
};

const origOptionsDesc = Object.getOwnPropertyDescriptor(
    CalendarCommonRenderer.prototype,
    "options"
);
if (origOptionsDesc?.get) {
    const origGet = origOptionsDesc.get;
    Object.defineProperty(CalendarCommonRenderer.prototype, "options", {
        get() {
            const opts = origGet.call(this);
            const meta = this.props.model?.meta;
            if (meta?.resModel === "spa.service.booking") {
                opts.minTime =
                    meta.spa_calendar_min_time || DEFAULT_MIN_TIME;
                opts.maxTime =
                    meta.spa_calendar_max_time || DEFAULT_MAX_TIME;
                // Do not visually overlap events in the same slot; render them as narrower columns.
                // This makes dense schedules readable.
                opts.slotEventOverlap = false;
                // if (meta.spa_calendar_content_height > 0) {
                //     opts.contentHeight = meta.spa_calendar_content_height;
                //     opts.height = meta.spa_calendar_content_height;
                // }
            }
            return opts;
        },
        // Keep original descriptor flags; avoids Owl "capture" assigning to getter
        configurable: origOptionsDesc.configurable,
        enumerable: origOptionsDesc.enumerable,
    });
}

// Disable hover highlight/expand effect for SPA booking calendar.
// Core adds class `o_cw_custom_highlight` on mouseenter, which can be distracting
// when many events are close together. Click already opens details.
const _origOnEventMouseEnter = CalendarCommonRenderer.prototype.onEventMouseEnter;
const _origOnEventMouseLeave = CalendarCommonRenderer.prototype.onEventMouseLeave;
CalendarCommonRenderer.prototype.onEventMouseEnter = function(info) {
    const meta = this.props?.model?.meta;
    if (meta?.resModel === "spa.service.booking") {
        return;
    }
    return _origOnEventMouseEnter.call(this, info);
};
CalendarCommonRenderer.prototype.onEventMouseLeave = function(info) {
    const meta = this.props?.model?.meta;
    if (meta?.resModel === "spa.service.booking") {
        return;
    }
    return _origOnEventMouseLeave.call(this, info);
};

// Also disable highlight on click/drag (core uses the same class).
const _origHighlightEvent = CalendarCommonRenderer.prototype.highlightEvent;
const _origUnhighlightEvent = CalendarCommonRenderer.prototype.unhighlightEvent;
CalendarCommonRenderer.prototype.highlightEvent = function(event, className) {
    const meta = this.props?.model?.meta;
    if (meta?.resModel === "spa.service.booking" && className === "o_cw_custom_highlight") {
        return;
    }
    return _origHighlightEvent.call(this, event, className);
};
CalendarCommonRenderer.prototype.unhighlightEvent = function(event, className) {
    const meta = this.props?.model?.meta;
    if (meta?.resModel === "spa.service.booking" && className === "o_cw_custom_highlight") {
        return;
    }
    return _origUnhighlightEvent.call(this, event, className);
};

// updateSize() mặc định set height theo cửa sổ → ghi đè. Dùng chiều cao cấu hình khi có.
const originalUpdateSize = CalendarCommonRenderer.prototype.updateSize;

function _parsePx(value) {
    if (!value) return 0;
    const n = parseInt(String(value).replace("px", ""), 10);
    return Number.isFinite(n)?n : 0;
}

function _applyStableHeight(renderer) {
    const meta = renderer.props?.model?.meta;
    if (!meta || meta.resModel !== "spa.service.booking" || !renderer.fc?.el) {
        return;
    }
    const el = renderer.fc.el;
    const nextHeight = _parsePx(el.style.height);
    const stable = _parsePx(meta.spa_calendar_stable_height);

    // First good measurement becomes the stable height.
    // If later computations shrink (common during fast re-render), keep stable height.
    if (nextHeight > stable) {
        meta.spa_calendar_stable_height = `${nextHeight}px`;
        el.style.minHeight = `${nextHeight}px`;
    } else if (stable > 0 && nextHeight > 0 && nextHeight < stable) {
        el.style.height = `${stable}px`;
        el.style.minHeight = `${stable}px`;
    }
}

CalendarCommonRenderer.prototype.updateSize = function() {
    const meta = this.props.model?.meta;
    const isSpaBooking = meta?.resModel === "spa.service.booking";
    const pxPerHour = isSpaBooking ?
        (meta.spa_calendar_pixels_per_hour??DEFAULT_PIXELS_PER_HOUR) :
        null;

    // Always run core sizing logic first; it sets height based on viewport.
    const res = originalUpdateSize.call(this);

    if (isSpaBooking && this.fc?.el) {
        this.fc.el.classList.add("o_calendar_spa_booking");
        this.fc.el.style.setProperty("--spa-pixels-per-hour", String(pxPerHour));
        this.fc.el.closest(".o_calendar_container")?.classList.add("o_calendar_spa_booking_view");

        // Apply stable height immediately.
        _applyStableHeight(this);

        // Re-apply stable height in next frame: core can measure wrong during transition.
        requestAnimationFrame(() => {
            _applyStableHeight(this);
            this.fc?.api?.updateSize?.();
        });
    }
    return res;
};


CalendarController.components = {
    ...CalendarController.components,
    SpaCalendarHeightSelector,
};
CalendarController.prototype.reloadCalendarConfig = async function() {
    if (this.props?.resModel !== "spa.service.booking") {
        return this.model.load({});
    }
    const res = await this.model.load({});
    return res;
};

CalendarController.prototype.openShiftConfigWizard = async function() {
    if (this.props?.resModel !== "spa.service.booking") {
        return;
    }
    // Use the currently displayed calendar date (local) so duration=0 means "rest today".
    const luxonDate = this.date;
    const shiftDate = luxonDate?.toISODate?luxonDate.toISODate() : null;
    const action = await this.orm.call(
        "booking.shift.config",
        "action_open_config_modal",
        shiftDate?[shiftDate]:[]
    );
    return this.action.doAction(action);
};

// ——— Giữ scale khi chọn ngày từ calendar nhỏ (chỉ áp dụng cho đặt lịch SPA) ———
// Core Odoo: datePickerProps.onSelect khi click cùng ngày thì cycle scale (day→week→month),
// khi click ngày khác trong tuần thì ép scale="day" → lịch nhảy lung tung.
// Ghi đè getter để với spa.service.booking chỉ load lại với date mới, giữ nguyên scale.
const origDatePickerPropsDesc = Object.getOwnPropertyDescriptor(
    CalendarController.prototype,
    "datePickerProps"
);
if (origDatePickerPropsDesc && typeof origDatePickerPropsDesc.get === "function") {
    const origGet = origDatePickerPropsDesc.get;
    Object.defineProperty(CalendarController.prototype, "datePickerProps", {
        get() {
            const props = origGet.call(this);
            if (this.props?.resModel === "spa.service.booking") {
                return {
                    ...props,
                    onSelect: async (date) => {
                        await this.model.load({
                            date
                        });
                    },
                };
            }
            return props;
        },
        // Keep original descriptor flags; important for Owl "capture" behavior
        configurable: origDatePickerPropsDesc.configurable,
        enumerable: origDatePickerPropsDesc.enumerable,
    });
}

const calendarView = registry.category("views").get("calendar");
const originalProps = calendarView.props;

calendarView.props = (props, view) => {
    const result = originalProps(props, view);
    if (props.resModel === "spa.service.booking") {
        result.buttonTemplate = "spa.CalendarController.controlButtons";
        result.Renderer = SpaBookingCalendarRenderer;
    }
    return result;
};
