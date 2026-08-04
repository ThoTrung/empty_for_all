/** @odoo-module **/

/**
 * Custom filter DomainSelector does not pass field.domain to Many2one
 * autocomplete (makeAutoCompleteEditor omits it). SearchBar Domain.toList()
 * without context also drops domains using allowed_company_ids.
 *
 * Verified on DB rental: name_search([]) returns Administrator / companies;
 * name_search with customer_type=driver returns only drivers.
 */
import { Domain } from "@web/core/domain";
import { session } from "@web/session";
import { patch } from "@web/core/utils/patch";
import { TreeEditor } from "@web/core/tree_editor/tree_editor";
import { SearchBar } from "@web/search/search_bar/search_bar";
import { RecordAutocomplete } from "@web/core/record_selectors/record_autocomplete";
import { DomainSelectorAutocomplete, DomainSelectorSingleAutocomplete } from "@web/core/tree_editor/tree_editor_autocomplete";
import { registry } from "@web/core/registry";
import { _t } from "@web/core/l10n/translation";

const RELATIONAL_TYPES = new Set(["many2one", "many2many", "one2many"]);
const RELATIONAL_OPS = new Set(["in", "not in", "=", "!=", "parent_of", "child_of"]);
const SEARCH_MORE_LIMIT = 320;

/** Fallback when field.domain is missing from DomainSelector fieldDefs. */
const FALLBACK_DOMAINS_BY_PATH = {
    "rr.transport|driver_id": [
        ["customer_type", "=", "driver"],
        ["is_company", "=", false],
    ],
    "rental.transport.import.wizard|default_driver_id": [
        ["customer_type", "=", "driver"],
        ["is_company", "=", false],
    ],
    "rental.contract|a_company_party": [
        ["is_rental_customer", "=", true],
        ["is_company", "=", true],
    ],
    "rental.analytics.on.hire.line|partner_company_id": [
        ["is_rental_customer", "=", true],
        ["is_company", "=", true],
    ],
    "account.move|rental_partner_company_id": [
        ["is_rental_customer", "=", true],
        ["is_company", "=", true],
    ],
};

/** fieldString fallback (translated labels from fields_get / get_views). */
const FALLBACK_DOMAINS_BY_STRING = {
    "Tài xế": [
        ["customer_type", "=", "driver"],
        ["is_company", "=", false],
    ],
    Driver: [
        ["customer_type", "=", "driver"],
        ["is_company", "=", false],
    ],
    "Tài xế mặc định": [
        ["customer_type", "=", "driver"],
        ["is_company", "=", false],
    ],
};

function buildEvalContext(env) {
    return {
        ...session.user_context,
        ...(env?.services?.user?.context || {}),
        uid: session.uid || session.user_id,
    };
}

function evalDomain(domain, env) {
    if (!domain) {
        return null;
    }
    try {
        return new Domain(domain).toList(buildEvalContext(env));
    } catch {
        return null;
    }
}

function resolveFieldDomain(fieldDef, resModel, path, env) {
    const fromField = evalDomain(fieldDef?.domain, env);
    if (fromField && fromField.length) {
        return fromField;
    }
    if (resModel && path && FALLBACK_DOMAINS_BY_PATH[`${resModel}|${path}`]) {
        return FALLBACK_DOMAINS_BY_PATH[`${resModel}|${path}`];
    }
    const label = fieldDef?.string;
    if (label && FALLBACK_DOMAINS_BY_STRING[label]) {
        return FALLBACK_DOMAINS_BY_STRING[label];
    }
    return null;
}

function wrapExtractProps(info, domain) {
    if (!info?.extractProps || !domain) {
        return info;
    }
    const originalExtract = info.extractProps;
    return {
        ...info,
        extractProps: (params) => {
            const props = originalExtract(params) || {};
            // Always force domain — core omits it entirely.
            props.domain = domain;
            props.context = {
                ...(props.context || {}),
                rental_partner_name_search_domain: domain,
            };
            return props;
        },
    };
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
        const domain = resolveFieldDomain(
            fieldDef,
            this.props.resModel,
            node.path,
            this.env
        );
        return wrapExtractProps(info, domain);
    },

    async updatePath(node, path) {
        await super.updatePath(node, path);
        // Core updatePath loads fieldDef but does not store it on this.fieldDefs.
        if (typeof path === "string" && this.fieldDefs) {
            const { fieldDef } = await this.loadFieldInfo(this.props.resModel, path);
            if (fieldDef) {
                this.fieldDefs[path] = fieldDef;
            }
        }
    },
});

patch(SearchBar.prototype, {
    async computeSubItems(searchItem, query) {
        if (searchItem.domain) {
            try {
                const evaluated = new Domain(searchItem.domain).toList(
                    this.env.searchModel.domainEvalContext
                );
                searchItem = { ...searchItem, domain: evaluated };
            } catch {
                // keep original
            }
        }
        return super.computeSubItems(searchItem, query);
    },
});

/**
 * Last-resort: even if DomainSelector never passes domain, filter by field label.
 * Fixes "Sửa đổi điều kiện" → Tài xế suggesting all res.partner.
 */
function partnerFallbackDomain(props) {
    if (props.resModel !== "res.partner") {
        return null;
    }
    if (props.domain && props.domain.length) {
        return null; // already scoped
    }
    const label = props.fieldString;
    return (label && FALLBACK_DOMAINS_BY_STRING[label]) || null;
}

patch(RecordAutocomplete.prototype, {
    getDomain() {
        const domain = super.getDomain();
        const extra = partnerFallbackDomain(this.props);
        if (!extra) {
            return domain;
        }
        return Domain.and([domain, extra]).toList();
    },

    async onSearchMore(name) {
        const { fieldString, multiSelect, resModel } = this.props;
        let operator;
        const ids = [];
        if (name) {
            const nameGets = await this.search(name, SEARCH_MORE_LIMIT);
            this.addNames(nameGets);
            operator = "in";
            ids.push(...nameGets.map((nameGet) => nameGet[0]));
        } else {
            operator = "not in";
            ids.push(...this.getIds());
        }
        const dynamicFilters = ids.length
            ? [
                  {
                      description: _t("Quick search: %s", name),
                      domain: [["id", operator, ids]],
                  },
              ]
            : undefined;
        const SelectCreateDialog = registry.category("dialogs").get("select_create");
        const fallback = partnerFallbackDomain(this.props);
        this.addDialog(SelectCreateDialog, {
            title: _t("Search: %s", fieldString),
            dynamicFilters,
            resModel,
            noCreate: true,
            multiSelect,
            domain: this.props.domain?.length
                ? this.props.domain
                : fallback || [],
            context: this.props.context || {},
            onSelected: (resId) => {
                const resIds = Array.isArray(resId) ? resId : [resId];
                this.props.update([...resIds]);
            },
        });
    },
});

// DomainSelector autocomplete classes inherit RecordAutocomplete via MultiRecordSelector.
// Patching RecordAutocomplete is enough for getDomain; ensure props.domain still preferred.

void DomainSelectorAutocomplete;
void DomainSelectorSingleAutocomplete;
