/** @odoo-module **/

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";
import { useOpenX2ManyRecord, useX2ManyCrud } from "@web/views/fields/relational_utils";

/**
 * Tab "Phiếu giao - nhận VT" của HĐ: "Lưu & đóng" / "Lưu & tạo mới" trong modal phiếu
 * lưu luôn hợp đồng (ghi DB) thay vì chỉ đưa phiếu vào danh sách tạm.
 * Lưu HĐ lỗi → Odoo báo lỗi, phiếu vẫn nằm trong danh sách, HĐ còn chưa lưu.
 */
export class RentalTransportX2ManyField extends X2ManyField {
    setup() {
        super.setup();
        const { saveRecord, updateRecord } = useX2ManyCrud(() => this.list, false);
        const andSaveContract = (fn) => async (record) => {
            const res = await fn(record);
            await this.props.record.save();
            return res;
        };
        const openRecord = useOpenX2ManyRecord({
            resModel: this.list.resModel,
            activeField: this.activeField,
            activeActions: this.activeActions,
            getList: () => this.list,
            saveRecord: andSaveContract(saveRecord),
            updateRecord: andSaveContract(updateRecord),
            isMany2Many: false,
        });
        this._openRecord = (params) => {
            const activeElement = document.activeElement;
            openRecord({
                ...params,
                onClose: () => {
                    if (activeElement) {
                        activeElement.focus();
                    }
                },
            });
        };
    }
}

registry.category("fields").add("rental_transport_one2many", {
    ...x2ManyField,
    component: RentalTransportX2ManyField,
});
