/** @odoo-module **/

import {
    Dialog
} from "@web/core/dialog/dialog";
import {
    onMounted
} from "@odoo/owl";
import {
    patch
} from "@web/core/utils/patch";

function getDialogContext(props) {
    if (props?.actionProps?.context) {
        return props.actionProps.context;
    }
    if (props?.context) {
        return props.context;
    }
    return {};
}

patch(Dialog.prototype, {
    setup() {
        super.setup(...arguments);
        const ctx = getDialogContext(this.props);
        this._modalSizeClass = ctx.size_class || null;
        onMounted(() => {
            const dlg = this.modalRef?.el?.querySelector(
                ".modal-dialog.modal-dialog-centered"
            );
            if (!dlg) {
                return;
            }
            let sizeClass = this._modalSizeClass;
            if (!sizeClass && this.modalRef?.el?.querySelector(".o_rr_transport_form")) {
                sizeClass = "modal-xl";
            }
            if (!sizeClass) {
                return;
            }
            const oldSize = Array.from(dlg.classList).find((c) =>
                /^modal-(sm|md|lg|xl|fullscreen)$/.test(c)
            );
            if (oldSize) {
                dlg.classList.remove(oldSize);
            }
            dlg.classList.add(sizeClass);
        });
    },
});
