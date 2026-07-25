from odoo import models, fields


class ConstructionProject(models.Model):
    _name = "construction.project"
    _description = "Dự án công trình"
    _inherit = ["mc.group.mixin"]

    name = fields.Char(string="Tên dự án", required=True)


class ConstructionAddress(models.Model):
    _name = "construction.address"
    _description = "Địa chỉ công trình"
    _inherit = ["mc.group.mixin"]

    name = fields.Char(string="Địa chỉ", required=True)

