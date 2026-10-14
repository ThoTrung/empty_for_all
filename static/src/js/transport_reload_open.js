/** @odoo-module **/

import { registry } from "@web/core/registry";

/**
 * Reload controller hiện tại (form hợp đồng → list tab "Phiếu giao - nhận VT" cập nhật,
 * đóng các dialog) rồi chạy action `params.next` (mở lại phiếu trong modal).
 * Dùng bởi rr.transport._rental_action_reload_and_open.
 */
async function rentalReloadAndOpen(env, action) {
    const controller = env.services.action.currentController;
    if (controller) {
        await env.services.action.restore(controller.jsId);
    }
    return action.params && action.params.next;
}

registry.category("actions").add("rental_reload_and_open", rentalReloadAndOpen);
