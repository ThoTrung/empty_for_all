/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component, useExternalListener, useState } from "@odoo/owl";

const ICON_BASE = "/rental/static/src/img/dashboard/";

/**
 * Để đổi icon: chỉ cần ghi đè file ảnh cùng tên trong thư mục
 * rental/static/src/img/dashboard/ (không cần sửa file này).
 * Thứ tự các ô dưới đây quyết định vị trí hiển thị trên lưới
 * (5 ô đầu ở hàng 1, 4 ô sau ở hàng 2 - lệch phải 1 cột).
 */
const TILES = [
    {
        id: "hop_dong",
        label: "Hợp đồng",
        icon: ICON_BASE + "icon_hopdong.svg",
        action: "rental.action_rental_contract",
    },
    {
        id: "hoa_don",
        label: "Hóa đơn",
        icon: ICON_BASE + "icon_hoadon.svg",
        action: "rental.action_move_out_invoice_and_refund_type",
    },
    {
        id: "khoi_luong",
        label: "Bảng xác nhận khối lượng",
        icon: ICON_BASE + "icon_khoiluong.svg",
        action: "rental.action_rental_transport_matrix",
    },
    {
        id: "khach_hang",
        label: "Khách hàng",
        icon: ICON_BASE + "icon_khachhang.svg",
        action: "rental.action_res_partner_renters",
    },
    {
        id: "ban_hang",
        label: "Bán hàng",
        icon: ICON_BASE + "icon_banhang.svg",
        action: "sale.action_orders",
    },
    {
        id: "mua_hang",
        label: "Mua hàng",
        icon: ICON_BASE + "icon_muahang.svg",
        action: "purchase.purchase_form_action",
    },
    {
        id: "danh_muc",
        label: "Danh mục",
        icon: ICON_BASE + "icon_danhmuc.svg",
        children: [
            {
                id: "vat_tu",
                label: "Vật tư",
                icon: ICON_BASE + "icon_vattu.svg",
                action: "rental.action_rental_product_templates",
            },
            {
                id: "chi_tiet_vat_tu",
                label: "Chi tiết vật tư",
                icon: ICON_BASE + "icon_chitietvattu.svg",
                action: "rental.action_rental_product_variants",
            },
            {
                id: "khach_hang_ncc",
                label: "Khách hàng/NCC",
                icon: ICON_BASE + "icon_khachhang.svg",
                action: "rental.action_res_partner_renters",
            },
            {
                id: "tai_xe",
                label: "Tài xế",
                icon: ICON_BASE + "icon_taixe.svg",
                action: "rental.action_res_partner_drivers",
            },
            {
                id: "xe",
                label: "Xe",
                icon: ICON_BASE + "icon_xe.svg",
                action: "rental.action_transport_truck",
            },
            {
                id: "cong_trinh",
                label: "Công trình",
                icon: ICON_BASE + "icon_congtrinh.svg",
                action: "rental.action_construction_work",
            },
            {
                id: "dia_chi_cong_trinh",
                label: "Địa chỉ công trình",
                icon: ICON_BASE + "icon_diachicongtrinh.svg",
                action: "rental.action_construction_address",
            },
        ],
    },
    {
        id: "kho",
        label: "Kho",
        icon: ICON_BASE + "icon_kho.svg",
        action: "stock.stock_picking_type_action",
    },
    {
        id: "van_chuyen",
        label: "Vận chuyển",
        icon: ICON_BASE + "icon_vanchuyen.svg",
        action: "rental.action_rr_transport",
    },
];

export class RentalHomeDashboard extends Component {
    setup() {
        this.action = useService("action");
        this.state = useState({ openDropdownId: null });
        useExternalListener(window, "click", this.onWindowClick, { capture: true });

        // Hàng 1: 5 ô | Hàng 2: 1 ô trống + 4 ô (khớp bố cục ảnh mẫu)
        this.gridItems = [...TILES.slice(0, 5), { id: "blank", blank: true }, ...TILES.slice(5, 9)];
    }

    onWindowClick(ev) {
        if (!this.state.openDropdownId) {
            return;
        }
        if (!ev.target.closest(`.o_rental_home_tile[data-tile-id="${this.state.openDropdownId}"]`)) {
            this.state.openDropdownId = null;
        }
    }

    onTileClick(tile) {
        if (tile.blank) {
            return;
        }
        if (tile.children) {
            this.state.openDropdownId = this.state.openDropdownId === tile.id ? null : tile.id;
            return;
        }
        this.state.openDropdownId = null;
        this.action.doAction(tile.action);
    }

    onChildClick(child, ev) {
        ev.stopPropagation();
        this.state.openDropdownId = null;
        this.action.doAction(child.action);
    }
}
RentalHomeDashboard.template = "rental.HomeDashboard";
RentalHomeDashboard.props = { ...standardActionServiceProps };

registry.category("actions").add("rental_home_dashboard", RentalHomeDashboard);
