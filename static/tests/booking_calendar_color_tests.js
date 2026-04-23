/** @odoo-module **/

import { applySpaBookingEventColors } from "../src/js/spa_booking_calendar_renderer";

QUnit.module("booking_calendar", (hooks) => {
    QUnit.test("applySpaBookingEventColors sets background + fg vars", async (assert) => {
        const el = document.createElement("div");
        el.className = "fc-event";
        const bg = document.createElement("div");
        bg.className = "fc-bg";
        el.appendChild(bg);

        const record = {
            rawRecord: {
                state_calendar_hex_color: "#e63946",
                state_calendar_hex_text_color: "#fff",
            },
        };

        applySpaBookingEventColors(el, record);

        assert.equal(el.style.getPropertyValue("--o-event-bg"), "#e63946");
        assert.equal(el.style.backgroundColor, "rgb(230, 57, 70)");
        assert.equal(el.style.getPropertyValue("--spa-event-fg"), "#fff");
        assert.equal(bg.style.backgroundColor, "rgb(230, 57, 70)");
        assert.equal(bg.style.opacity, "1");
    });

    QUnit.test("applySpaBookingEventColors normalizes missing #", async (assert) => {
        const el = document.createElement("div");
        const bg = document.createElement("div");
        bg.className = "fc-bg";
        el.appendChild(bg);

        const record = {
            rawRecord: {
                state_calendar_hex_color: "abc",
                state_calendar_hex_text_color: "000",
            },
        };
        applySpaBookingEventColors(el, record);
        assert.equal(el.style.getPropertyValue("--o-event-bg"), "#abc");
        assert.equal(el.style.getPropertyValue("--spa-event-fg"), "#000");
    });

    QUnit.test("applySpaBookingEventColors no-ops without background color", async (assert) => {
        const el = document.createElement("div");
        const record = { rawRecord: { state_calendar_hex_color: "" } };
        applySpaBookingEventColors(el, record);
        assert.equal(el.style.getPropertyValue("--o-event-bg"), "");
        assert.equal(el.style.getPropertyValue("--spa-event-fg"), "");
    });

    QUnit.test("applySpaBookingEventColors prefers draft special colors", async (assert) => {
        const el = document.createElement("div");
        const bg = document.createElement("div");
        bg.className = "fc-bg";
        el.appendChild(bg);

        const record = {
            rawRecord: {
                state: "draft",
                state_calendar_hex_color: "#2a9d8f",
                state_calendar_hex_text_color: "#000",
                draft_special_hex_color: "#3E51BA",
                draft_special_hex_text_color: "#fff",
            },
        };
        applySpaBookingEventColors(el, record);
        assert.equal(el.style.getPropertyValue("--o-event-bg"), "#3E51BA");
        assert.equal(el.style.getPropertyValue("--spa-event-fg"), "#fff");
    });
});

