/** @odoo-module **/

import {
    Component,
    useState
} from "@odoo/owl";

import {
    useService
} from "@web/core/utils/hooks";

const HEIGHT_OPTIONS = [{
        value: 60,
        label: "60 px/giờ"
    },
    {
        value: 80,
        label: "80 px/giờ"
    },
    {
        value: 100,
        label: "100 px/giờ"
    },
    {
        value: 120,
        label: "120 px/giờ"
    },
    {
        value: 160,
        label: "160 px/giờ"
    },
    {
        value: 200,
        label: "200 px/giờ"
    },
    {
        value: 240,
        label: "240 px/giờ"
    },
    {
        value: 280,
        label: "280 px/giờ"
    },
    {
        value: 320,
        label: "320 px/giờ"
    },
    {
        value: 360,
        label: "360 px/giờ"
    },
];

export class SpaCalendarHeightSelector extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            pixelsPerHour: this.props.model?.meta?.spa_calendar_pixels_per_hour?? 80,
            minTime: this.props.model?.meta?.spa_calendar_min_time ?? "05:00:00",
            maxTime: this.props.model?.meta?.spa_calendar_max_time ?? "22:00:00",
            saving: false,
        });
    }

    get options() {
        return HEIGHT_OPTIONS;
    }

    get currentPixelsPerHour() {
        const v = this.props.model?.meta?.spa_calendar_pixels_per_hour;
        if (v != null) return v;
        return this.state.pixelsPerHour;
    }

    get currentMinTime() {
        const v = this.props.model?.meta?.spa_calendar_min_time;
        if (v != null) return v;
        return this.state.minTime;
    }

    get currentMaxTime() {
        const v = this.props.model?.meta?.spa_calendar_max_time;
        if (v != null) return v;
        return this.state.maxTime;
    }

    async saveAndReload(payload) {
        this.state.saving = true;
        try {
            await this.orm.call(
                "spa.service.booking",
                "set_calendar_display_config",
                [],
                payload
            );
            if (typeof this.props.onChanged === "function") {
                await this.props.onChanged();
            }
        } finally {
            this.state.saving = false;
        }
    }

    async onHeightChange(ev) {
        const value = parseInt(ev.target.value, 10);
        if (value < 40 || value > 360) return;
        this.state.pixelsPerHour = value;
        await this.saveAndReload({
            pixels_per_hour: value
        });
    }

    async onMinTimeChange(ev) {
        const v = String(ev.target.value || "").trim() || "05:00:00";
        this.state.minTime = v;
        await this.saveAndReload({
            min_time: v
        });
    }

    async onMaxTimeChange(ev) {
        const v = String(ev.target.value || "").trim() || "22:00:00";
        this.state.maxTime = v;
        await this.saveAndReload({
            max_time: v
        });
    }
}

SpaCalendarHeightSelector.template = "spa.SpaCalendarHeightSelector";
SpaCalendarHeightSelector.props = {
    model: Object,
    resModel: String,
    onChanged: {
        type: Function,
        optional: true
    },
};