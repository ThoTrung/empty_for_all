# -*- coding: utf-8 -*-

from odoo import api, fields, models
from odoo.exceptions import ValidationError


class GaraSurveyTemplate(models.Model):
    _name = 'gara.survey.template'
    _description = 'Gara customer survey template'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    group_ids = fields.One2many('gara.survey.question.group', 'template_id')
    question_ids = fields.One2many('gara.survey.question', 'template_id')


class GaraSurveyQuestionGroup(models.Model):
    _name = 'gara.survey.question.group'
    _description = 'Gara survey question group'
    _order = 'template_id, sequence, id'

    name = fields.Char(required=True)
    template_id = fields.Many2one('gara.survey.template', required=True, ondelete='cascade')
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    question_ids = fields.One2many('gara.survey.question', 'group_id')


class GaraSurveyQuestion(models.Model):
    _name = 'gara.survey.question'
    _description = 'Gara survey question'
    _order = 'sequence, id'

    template_id = fields.Many2one('gara.survey.template', required=True, ondelete='cascade')
    group_id = fields.Many2one(
        'gara.survey.question.group',
        domain="[('template_id', '=', template_id)]",
        ondelete='set null',
    )
    sequence = fields.Integer(default=10)
    text = fields.Char(required=True)

    @api.constrains('template_id', 'group_id')
    def _check_group_template(self):
        for question in self:
            if question.group_id and question.group_id.template_id != question.template_id:
                raise ValidationError('Question group must belong to the same survey template.')


class GaraSurveyResponse(models.Model):
    _name = 'gara.survey.response'
    _description = 'Gara customer survey response'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(required=True, default='Survey')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    case_id = fields.Many2one('gara.workshop.case', ondelete='set null')
    partner_id = fields.Many2one('res.partner', required=True)
    template_id = fields.Many2one('gara.survey.template')
    line_ids = fields.One2many('gara.survey.response.line', 'response_id')
    score_avg = fields.Float(compute='_compute_score_avg', store=True)
    note = fields.Html()

    @api.depends('line_ids.score')
    def _compute_score_avg(self):
        for rec in self:
            scores = rec.line_ids.mapped('score')
            rec.score_avg = sum(scores) / len(scores) if scores else 0.0


class GaraSurveyResponseLine(models.Model):
    _name = 'gara.survey.response.line'
    _description = 'Gara survey response line'

    response_id = fields.Many2one('gara.survey.response', required=True, ondelete='cascade')
    question_id = fields.Many2one('gara.survey.question')
    score = fields.Integer(default=5)
    answer_text = fields.Char()
