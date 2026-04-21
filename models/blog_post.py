from odoo import api, models, fields, _
from odoo.tools.translate import html_translate


class BlogPost(models.Model):
    _inherit = "blog.post"
    _order = 'sequence, id'

    sequence = fields.Integer(string='Sequence', default=100)
    snippet_image_1920 = fields.Image(
        string="Snippet Image",
        max_width=1920,
        max_height=1920,
        help="Image used in blog snippets, cards, and lists"
    )

    post_type = fields.Selection(
        selection=[
            ("blog", "News"),
            ("daily_tour", "Daily tour"),
            ("boat_rental", "Boat rental"),
            ("gallery", "Gallery"),
        ],
        default="blog",
        required=True,
        index=True,
    )

    tour_hero_image = fields.Image(
        string="Tour map image",
        max_width=1920,
        max_height=1920,
        help="Image use in Detail blog that full width, it is the map of destination."
    )
    banner_image = fields.Image(
        string="Banner",
        max_width=1920,
        max_height=1920,
        help="Banner for each blog replace the default."
    )
    banner_image_pc = fields.Image(string="Banner (Desktop)", max_width=2560, max_height=1440)
    banner_image_mb = fields.Image(string="Banner (Mobile)", max_width=1440, max_height=2560)

    short_content = fields.Html(
        'Short content',
        translate=html_translate, sanitize=False,
        default="""
<p>Lịch trình<strong>&nbsp;từ 15:00 chiều – 21:00 tối Thứ 7</strong>&nbsp;hằng tuần</p>
<p>Khời hành tại&nbsp;<strong>Bến tàu du lịch Nha Trang</strong></p>
"""
    )

    # Canonical website URL for all posts (flat slug)
    # website_url = fields.Char(compute="_compute_website_url", readonly=True)

    _sql_constraints = [
        # Global unique slug across all blog.post
        ("blog_post_slug_unique", "unique(slug)", "Slug must be unique across all content."),
    ]

    # @api.depends("slug")
    # def _compute_website_url(self):
    #     pass
    #     for rec in self:
    #         # Ensure always canonical /<slug>
    #         rec.website_url = f"/{rec.slug}" if rec.slug else "/"
    #
    # @api.constrains("slug")
    # def _check_slug_not_empty(self):
    #     for rec in self:
    #         # blog.post normally manages slug, but enforce not empty for published records
    #         if rec.website_published and not rec.slug:
    #             raise ValidationError(_("Published content must have a slug."))

    # @api.model_create_multi
    # def create(self, vals_list):
    #     records = super().create(vals_list)
    #     # Defensive: if a duplicate slug slipped past UI, SQL constraint will block
    #     return records
    #
    # def write(self, vals):
    #     return super().write(vals)
