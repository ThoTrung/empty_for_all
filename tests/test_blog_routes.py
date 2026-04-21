from odoo.addons.http_routing.models.ir_http import slug
from odoo.tests import tagged
from odoo.tests.common import HttpCase


@tagged("-at_install", "post_install")
class TestLuxboatBlogRoutes(HttpCase):
    def setUp(self):
        super().setUp()
        self.website = self.env["website"].search([], limit=1)
        self.blog = self.env["blog.blog"].create({
            "name": "Luxboat Blog",
            "website_id": self.website.id,
        })
        self.posts = {}
        for post_type in ("blog", "daily_tour", "boat_rental", "gallery"):
            self.posts[post_type] = self.env["blog.post"].create({
                "name": f"Post {post_type}",
                "blog_id": self.blog.id,
                "post_type": post_type,
                "website_published": True,
            })

    def _assert_ok(self, path, marker):
        response = self.url_open(path)
        self.assertEqual(response.status_code, 200)
        self.assertIn(marker, response.text)

    def test_list_routes(self):
        self._assert_ok("/tin-tuc", "o_blog_custom_list")
        self._assert_ok("/tat-ca-tin-tuc", "o_snippet_blog_5_best_recs")
        self._assert_ok("/dich-vu-tour-theo-ngay", "id_daily_tour_list_tpl")
        self._assert_ok("/dich-vu-thue-ca-tau", "id_boat_rental_list_tpl")
        self._assert_ok("/gallery", "id_gallery_list_tpl")
        self._assert_ok("/ha-long-bay", "id_luxboat_destination_list_tpl")

    def test_detail_template_routing(self):
        self._assert_ok(f"/{slug(self.posts['blog'])}", "o_wblog_post_page_cover")
        self._assert_ok(f"/{slug(self.posts['daily_tour'])}", "Daily Tour Cover")
        self._assert_ok(f"/{slug(self.posts['boat_rental'])}", "Boat Rental Cover")
        self._assert_ok(f"/{slug(self.posts['gallery'])}", "Gallery Cover")
