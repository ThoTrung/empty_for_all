/** @odoo-module **/

import { whenReady } from "@odoo/owl";
import { jsonrpc } from "@web/core/network/rpc_service";

function canUseStorage(type = "localStorage") {
    try {
        const s = window[type];
        const k = "__test__";
        s.setItem(k, "1");
        s.removeItem(k);
        return true;
    } catch {
        return false;
    }
}
function getItem(key, type) {
    if (!canUseStorage(type)) return null;
    return window[type].getItem(key);
}
function setItem(key, val, type) {
    if (!canUseStorage(type)) return;
    window[type].setItem(key, val);
}

function shouldShowPopup(popup) {
    const id = popup.id;
    const freq = popup.show_frequency;

    if (freq === "always") return true;

    if (freq === "session") {
        return !getItem(`lux_popup_session_${id}`, "sessionStorage");
    }
    if (freq === "ever") {
        return !getItem(`lux_popup_ever_${id}`, "localStorage");
    }
    if (freq === "days") {
        const days = popup.frequency_days || 0;
        const last = parseInt(getItem(`lux_popup_days_${id}`, "localStorage") || "0", 10);
        if (!last) return true;
        return (Date.now() - last) >= (days * 86400000);
    }
    return true;
}

function markShown(popup) {
    const id = popup.id;
    const freq = popup.show_frequency;

    if (freq === "session") setItem(`lux_popup_session_${id}`, "1", "sessionStorage");
    if (freq === "ever") setItem(`lux_popup_ever_${id}`, "1", "localStorage");
    if (freq === "days") setItem(`lux_popup_days_${id}`, String(Date.now()), "localStorage");
}

function fillModal(modalEl, popup) {
    const img = modalEl.querySelector(".lux_popup_cover_img");
    const title = modalEl.querySelector(".lux_popup_title");
    const body = modalEl.querySelector(".lux_popup_body");
    const primary = modalEl.querySelector(".lux_popup_primary_btn");

    if (img) {
        if (popup.image_url) {
            img.src = popup.image_url;
            img.style.display = "";
        } else {
            img.style.display = "none";
        }
    }

    if (title) {
        if (popup.title) {
            title.textContent = popup.title;
            title.style.display = "";
        } else {
            title.style.display = "none";
        }
    }

    if (body) {
        body.innerHTML = popup.body_html || "";
    }

    if (primary) {
        primary.textContent = popup.primary_button_label || "OK";
        if (popup.primary_button_url) {
            primary.href = popup.primary_button_url;
            primary.target = "_self";
            primary.dataset.hasUrl = "1";
        } else {
            primary.href = "javascript:void(0)";
            primary.dataset.hasUrl = "0";
        }
    }
}

whenReady(async () => {
    const modalEl = document.getElementById("luxboat_website_popup_modal");
    if (!modalEl) return;

    // fetch popup from DB (already filtered by server)
    const res = await jsonrpc("/luxboat/popup/get", {});
    const popup = res && res.popup ? res.popup : null;
    if (!popup) return;

    // client-side frequency rule
    if (!shouldShowPopup(popup)) return;

    fillModal(modalEl, popup);

    const delay = Math.max(0, parseInt(popup.delay_ms || 0, 10));
    setTimeout(() => {
        const modal = Modal.getOrCreateInstance(modalEl, { backdrop: true, keyboard: true });
        modal.show();
        markShown(popup);
    }, delay);

    // If primary has no URL => close modal on click
    modalEl.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".lux_popup_primary_btn");
        if (!btn) return;
        if (btn.dataset.hasUrl === "0") {
            Modal.getOrCreateInstance(modalEl).hide();
        }
    });
});
