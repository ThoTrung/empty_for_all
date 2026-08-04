/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { loadBundle } from "@web/core/assets";
import { getColor } from "@web/core/colors/colors";
import { MultiRecordSelector } from "@web/core/record_selectors/multi_record_selector";
import { DateTimeInput } from "@web/core/datetime/datetime_input";
import { serializeDate, deserializeDate } from "@web/core/l10n/dates";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";

export class RentalAnalyticsBarChart extends Component {
    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
        });

        useEffect(
            () => {
                this.renderChart();
                return () => {
                    if (this.chart) {
                        this.chart.destroy();
                        this.chart = null;
                    }
                };
            },
            () => [
                this.props.labels,
                this.props.values,
                this.props.datasets,
                this.props.datasetLabel,
            ]
        );

        onWillUnmount(() => {
            if (this.chart) {
                this.chart.destroy();
                this.chart = null;
            }
        });
    }

    renderChart() {
        const canvas = this.canvasRef.el;
        if (!canvas || typeof Chart === "undefined") {
            return;
        }
        if (this.chart) {
            this.chart.destroy();
            this.chart = null;
        }
        const labels = this.props.labels || [];
        if (!labels.length) {
            return;
        }

        let datasets;
        if (this.props.datasets && this.props.datasets.length) {
            datasets = this.props.datasets.map((ds, index) => ({
                label: ds.label || "",
                data: ds.data || [],
                backgroundColor: getColor(index),
            }));
        } else {
            const values = this.props.values || [];
            const colors = labels.map((_label, index) => getColor(index));
            datasets = [
                {
                    label: this.props.datasetLabel || "",
                    data: values,
                    backgroundColor: colors,
                },
            ];
        }

        this.chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets,
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: Boolean(this.props.datasets && this.props.datasets.length > 1),
                    },
                },
                scales: {
                    x: {
                        ticks: {
                            maxRotation: 45,
                            minRotation: 0,
                            autoSkip: true,
                            maxTicksLimit: 12,
                        },
                    },
                    y: {
                        beginAtZero: true,
                    },
                },
            },
        });
    }
}
RentalAnalyticsBarChart.template = "rental.AnalyticsBarChart";
RentalAnalyticsBarChart.props = {
    labels: { type: Array },
    values: { type: Array, optional: true },
    datasets: { type: Array, optional: true },
    datasetLabel: { type: String, optional: true },
};

export class RentalAnalyticsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.companyService = useService("company");
        this.state = useState({
            loading: true,
            xntLoading: false,
            asOfDate: "",
            asOfDateDisplay: "",
            partnerCompanyIds: [],
            constructionWorkIds: [],
            warehouseIds: [],
            xntDateFrom: "",
            xntDateTo: "",
            widgets: [],
            xnt: null,
            error: null,
            xntError: null,
        });

        onWillStart(async () => {
            await this.loadFilterOptions();
            await Promise.all([this.loadDashboard(), this.loadXnt()]);
        });
    }

    get display() {
        return {
            controlPanel: {},
        };
    }

    get partnerDomain() {
        return [
            ["is_company", "=", true],
            ["is_rental_customer", "=", true],
            ["company_id", "in", this.companyService.activeCompanyIds],
        ];
    }

    get constructionWorkDomain() {
        return [
            ["company_id", "in", this.companyService.activeCompanyIds],
        ];
    }

    get warehouseDomain() {
        return [
            ["company_id", "in", this.companyService.activeCompanyIds],
        ];
    }

    get asOfDateValue() {
        return this.state.asOfDate ? deserializeDate(this.state.asOfDate) : false;
    }

    get xntDateFromValue() {
        return this.state.xntDateFrom ? deserializeDate(this.state.xntDateFrom) : false;
    }

    get xntDateToValue() {
        return this.state.xntDateTo ? deserializeDate(this.state.xntDateTo) : false;
    }

    async loadFilterOptions() {
        const options = await this.orm.call(
            "rental.analytics.dashboard",
            "get_filter_options",
            []
        );
        if (!this.state.asOfDate) {
            this.state.asOfDate = options.default_as_of_date;
        }
        if (!this.state.xntDateFrom) {
            this.state.xntDateFrom = options.default_xnt_date_from;
        }
        if (!this.state.xntDateTo) {
            this.state.xntDateTo = options.default_xnt_date_to;
        }
    }

    _filtersPayload(forceRefresh = false) {
        return {
            as_of_date: this.state.asOfDate,
            partner_company_ids: this.state.partnerCompanyIds || [],
            construction_work_ids: this.state.constructionWorkIds || [],
            warehouse_ids: this.state.warehouseIds || [],
            only_active_contracts: true,
            force_refresh: forceRefresh,
        };
    }

    _xntFiltersPayload() {
        return {
            ...this._filtersPayload(false),
            date_from: this.state.xntDateFrom,
            date_to: this.state.xntDateTo,
        };
    }

    async loadDashboard({ forceRefresh = false } = {}) {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call(
                "rental.analytics.dashboard",
                "get_dashboard_data",
                [],
                { filters: this._filtersPayload(forceRefresh) }
            );
            this.state.asOfDate = data.filters.as_of_date;
            this.state.asOfDateDisplay = data.as_of_date_display;
            this.state.partnerCompanyIds = (data.filters.partner_company_ids || []).map(
                (id) => Number(id)
            );
            this.state.constructionWorkIds = (
                data.filters.construction_work_ids || []
            ).map((id) => Number(id));
            this.state.warehouseIds = (data.filters.warehouse_ids || []).map((id) =>
                Number(id)
            );
            this.state.widgets = data.widgets || [];
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || `${error}`;
            this.state.widgets = [];
        } finally {
            this.state.loading = false;
        }
    }

    async loadXnt() {
        this.state.xntLoading = true;
        this.state.xntError = null;
        try {
            this.state.xnt = await this.orm.call(
                "rental.analytics.dashboard",
                "get_xnt_summary",
                [],
                { filters: this._xntFiltersPayload() }
            );
            if (this.state.xnt?.date_from) {
                this.state.xntDateFrom = this.state.xnt.date_from;
            }
            if (this.state.xnt?.date_to) {
                this.state.xntDateTo = this.state.xnt.date_to;
            }
        } catch (error) {
            this.state.xntError = error?.data?.message || error?.message || `${error}`;
            this.state.xnt = null;
        } finally {
            this.state.xntLoading = false;
        }
    }

    onAsOfDateChange(date) {
        this.state.asOfDate = date ? serializeDate(date) : "";
        this.loadDashboard();
    }

    onPartnerIdsUpdate(resIds) {
        this.state.partnerCompanyIds = (resIds || []).map((id) => Number(id));
        this.loadDashboard();
    }

    onConstructionWorkIdsUpdate(resIds) {
        this.state.constructionWorkIds = (resIds || []).map((id) => Number(id));
        this.loadDashboard();
    }

    onWarehouseIdsUpdate(resIds) {
        this.state.warehouseIds = (resIds || []).map((id) => Number(id));
        Promise.all([this.loadDashboard(), this.loadXnt()]);
    }

    onXntDateFromChange(date) {
        this.state.xntDateFrom = date ? serializeDate(date) : "";
        this.loadXnt();
    }

    onXntDateToChange(date) {
        this.state.xntDateTo = date ? serializeDate(date) : "";
        this.loadXnt();
    }

    async onRefresh() {
        await Promise.all([
            this.loadDashboard({ forceRefresh: true }),
            this.loadXnt(),
        ]);
    }

    async onOpenRentedQtyWizard() {
        await this.action.doAction("rental.action_rental_rented_qty_wizard");
    }

    async onOpenWidget(widget) {
        if (!widget?.detail_action) {
            return;
        }
        await this.action.doAction(widget.detail_action);
    }

    async onOpenXntFull() {
        const action = await this.orm.call(
            "rental.analytics.dashboard",
            "action_open_xnt_wizard",
            [],
            { filters: this._xntFiltersPayload() }
        );
        await this.action.doAction(action);
    }

    formatNumber(value) {
        const num = Number(value) || 0;
        return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
}
RentalAnalyticsDashboard.template = "rental.AnalyticsDashboard";
RentalAnalyticsDashboard.components = {
    Layout,
    RentalAnalyticsBarChart,
    MultiRecordSelector,
    DateTimeInput,
};
RentalAnalyticsDashboard.props = { ...standardActionServiceProps };

registry.category("actions").add("rental_analytics_dashboard", RentalAnalyticsDashboard);
