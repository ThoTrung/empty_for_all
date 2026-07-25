/** @odoo-module **/

/**
 * Odoo DomainSelector (custom filter "Sửa đổi điều kiện") does not pass
 * field.domain to Many2one autocomplete — so e.g. driver_id suggests all
 * res.partner. Inject evaluated field.domain when the editor supports it.
 */
import { Domain } from "@web/core/domain";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { TreeEditor } from "@web/core/tree_editor/tree_editor";

const RELATIONAL_TYPES = new Set(["many2one", "many2many", "one2many"]);
const RELATIONAL_OPS = new Set(["in", "not in", "=", "!=", "parent_of", "child_of"]);

function evalFieldDomain(fieldDef) {
    if (!fieldDef?.domain) {
        return null;
    }
    const context = {
        ...session.user_context,
        uid: session.uid || session.user_id,
    };
    try {
        return new Domain(fieldDef.domain).toList(context);
    } catch {
        // Dynamic domains that reference other record fields (e.g. parent_id = a_company_party)
        // cannot be evaluated in the filter editor — skip; form views still apply them.
        return null;
    }
}

patch(TreeEditor.prototype, {
    getValueEditorInfo(node) {
        const info = super.getValueEditorInfo(node);
        if (!RELATIONAL_OPS.has(node.operator) || !info?.extractProps) {
            return info;
        }
        const fieldDef = this.getFieldDef(node.path);
        if (!RELATIONAL_TYPES.has(fieldDef?.type)) {
            return info;
        }
        const domain = evalFieldDomain(fieldDef);
        if (!domain) {
            return info;
        }
        const originalExtract = info.extractProps;
        return {
            ...info,
            extractProps: (params) => {
                const props = originalExtract(params);
                if (props && props.domain === undefined) {
                    props.domain = domain;
                }
                return props;
            },
        };
    },
});
