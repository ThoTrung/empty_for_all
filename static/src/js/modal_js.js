/** @odoo-module **/

import { whenReady } from "@odoo/owl";

const STORAGE_KEY = "o_entry_modal_shown_v1";

function canUseLocalStorage() {
    try {
        const k = "__test__";
        localStorage.setItem(k, "1");
        localStorage.removeItem(k);
        return true;
    } catch {
        return false;
    }
}

function hasShown() {
    if (!canUseLocalStorage()) return false;
    return Boolean(localStorage.getItem(STORAGE_KEY));
}

function markShown() {
    if (!canUseLocalStorage()) return;
    localStorage.setItem(STORAGE_KEY, "1");
}

whenReady(() => {
    const modalEl = document.getElementById("o_entry_info_modal");
    if (!modalEl) return;

    // Do not show again if already shown
    if (hasShown()) return;

    // Delay a bit so page layout is stable
    setTimeout(() => {
        const modal = Modal.getOrCreateInstance(modalEl, {
            backdrop: true,     // click outside closes
            keyboard: true,     // ESC closes
        });
        modal.show();
        markShown();
    }, 500);

    // Example: primary button action
    modalEl.addEventListener("click", (ev) => {
        const btn = ev.target.closest(".o_entry_modal_primary");
        if (!btn) return;
        const modal = Modal.getOrCreateInstance(modalEl);
        modal.hide();
    });
});
