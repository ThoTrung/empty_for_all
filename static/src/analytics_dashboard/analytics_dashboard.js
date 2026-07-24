/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Layout } from "@web/search/layout";
import { loadBundle } from "@web/core/assets";
import { getColor } from "@web/core/colors/colors";
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
            () => [this.props.labels, this.props.values, this.props.datasetLabel]
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
        const values = this.props.values || [];
        if (!labels.length) {
            return;
        }
        const colors = labels.map((_label, index) => getColor(index));
        this.chart = new Chart(canvas, {
            type: "bar",
            data: {
                labels,
                datasets: [
                    {
                        label: this.props.datasetLabel || "",
                        data: values,
                        backgroundColor: colors,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
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
    values: { type: Array },
    datasetLabel: { type: String, optional: true },
};

export class RentalAnalyticsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            asOfDate: "",
            asOfDateDisplay: "",
            partnerCompanyId: "",
            constructionWorkId: "",
            partners: [],
            constructionWorks: [],
            widgets: [],
            error: null,
        });

        onWillStart(async () => {
            await this.loadFilterOptions();
            await this.loadDashboard();
        });
    }

    get display() {
        return {
            controlPanel: {},
        };
    }

    async loadFilterOptions() {
        const options = await this.orm.call(
            "rental.analytics.dashboard",
            "get_filter_options",
            []
        );
        this.state.partners = options.partners || [];
        this.state.constructionWorks = options.construction_works || [];
        if (!this.state.asOfDate) {
            this.state.asOfDate = options.default_as_of_date;
        }
    }

    _filtersPayload(forceRefresh = false) {
        return {
            as_of_date: this.state.asOfDate,
            partner_company_id: this.state.partnerCompanyId
                ? Number(this.state.partnerCompanyId)
                : false,
            construction_work_id: this.state.constructionWorkId
                ? Number(this.state.constructionWorkId)
                : false,
            only_active_contracts: true,
            force_refresh: forceRefresh,
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
            this.state.partnerCompanyId = data.filters.partner_company_id
                ? `${data.filters.partner_company_id}`
                : "";
            this.state.constructionWorkId = data.filters.construction_work_id
                ? `${data.filters.construction_work_id}`
                : "";
            this.state.widgets = data.widgets || [];
        } catch (error) {
            this.state.error = error?.data?.message || error?.message || `${error}`;
            this.state.widgets = [];
        } finally {
            this.state.loading = false;
        }
    }

    onAsOfDateChange(ev) {
        this.state.asOfDate = ev.target.value;
        this.loadDashboard();
    }

    onPartnerChange(ev) {
        this.state.partnerCompanyId = ev.target.value || "";
        this.loadDashboard();
    }

    onConstructionWorkChange(ev) {
        this.state.constructionWorkId = ev.target.value || "";
        this.loadDashboard();
    }

    async onRefresh() {
        await this.loadDashboard({ forceRefresh: true });
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

    formatNumber(value) {
        const num = Number(value) || 0;
        return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
    }
}
RentalAnalyticsDashboard.template = "rental.AnalyticsDashboard";
RentalAnalyticsDashboard.components = { Layout, RentalAnalyticsBarChart };

registry.category("actions").add("rental_analytics_dashboard", RentalAnalyticsDashboard);
