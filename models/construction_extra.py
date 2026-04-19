from odoo import models, fields


class ConstructionProject(models.Model):
    _name = "construction.project"
    _description = "Construction Project"
    _inherit = ["mc.group.mixin"]

    name = fields.Char(string="Project name", required=True)


class ConstructionAddress(models.Model):
    _name = "construction.address"
    _description = "Construction Address"
    _inherit = ["mc.group.mixin"]

    name = fields.Char(string="Address", required=True)

