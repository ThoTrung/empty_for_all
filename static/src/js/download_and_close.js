/** @odoo-module **/
import { registry } from "@web/core/registry";

function downloadAndCloseModal(env, action){
    /**
     * @param {Object} env - OWL env (has services)
     * @param {Object} action - the action dict returned from Python
     */
    const url = action.params && action.params.url;
    if (url) {
        // Same-document <a download> avoids popup blockers that kill
        // window.open() after the wizard Confirm RPC returns.
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", "");
        link.style.display = "none";
        document.body.appendChild(link);
        link.click();
        link.remove();
    }
    // Close the current wizard dialog
    env.services.action.doAction({ type: "ir.actions.act_window_close" });
}

registry.category("actions").add("download_and_close", downloadAndCloseModal);
