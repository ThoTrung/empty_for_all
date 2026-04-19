/** @odoo-module **/
import { registry } from "@web/core/registry";

function downloadAndCloseModal(env, action){
    /**
     * @param {Object} env - OWL env (has services)
     * @param {Object} action - the action dict returned from Python
     */
    const url = action.params && action.params.url;
    if (url) {
        // Open in a new tab so we can still run the close action here
        window.open(url, "_blank");
    }
    // Close the current wizard dialog
    env.services.action.doAction({ type: "ir.actions.act_window_close" });
}

registry.category("actions").add("download_and_close", downloadAndCloseModal);