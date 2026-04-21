from odoo import http
from odoo.http import request
from werkzeug.exceptions import NotFound
from odoo.addons.website_blog.controllers.main import WebsiteBlog


class BlogController(WebsiteBlog):
    @staticmethod
    def _post_domain(post_type):
        return [
            ("website_published", "=", True),
            ("post_type", "=", post_type),
            ("blog_id.website_id", "in", [False, request.website.id]),
        ]

    @staticmethod
    def _posts_env():
        # Public website pages need elevated rights to read published content.
        return request.env["blog.post"].sudo()

    """
    - Custom list page: /articles
    - Root detail URL: /<slug> (only if it's a blog.post)
    - 301 redirect old detail URL: /blog/<slug> -> /<slug>
    """

    # -----------------------------
    # Custom blog list page
    # -----------------------------
    @http.route(["/tin-tuc"], type="http", auth="public", website=True, sitemap=True)
    def blog_post_index(self, **kwargs):
        page = int(kwargs.get("page", 1))
        BlogPost = self._posts_env()
        domain = self._post_domain("blog")

        # Pagination
        step = 13
        total = BlogPost.search_count(domain)
        pager = request.website.pager(
            url="/tin-tuc",
            total=total,
            page=page,
            step=step,
            scope=7,
        )

        posts = BlogPost.search(domain, order="sequence asc, id desc", limit=step, offset=pager["offset"])
        records = posts[0:5]
        remaining = posts[5:]

        return request.render("luxboat.news_list", {
            "pager": pager,
            "records": records,
            "remaining": remaining,
        })

    @http.route([
        "/tat-ca-tin-tuc",
        "/tat-ca-tin-tuc/page/<int:page>",
    ], type="http", auth="public", website=True, sitemap=True)
    def all_blog_post_index(self, page=1, **kwargs):
        page = int(page)
        BlogPost = self._posts_env()
        domain = self._post_domain("blog")

        # Pagination
        step = 20
        total = BlogPost.search_count(domain)
        pager = request.website.pager(
            url="/tat-ca-tin-tuc",
            total=total,
            page=page,
            step=step,
            scope=7,
        )
        posts = BlogPost.search(domain, order="sequence asc, id desc", limit=step, offset=pager["offset"])
        return request.render("luxboat.all_news_list", {
            "pager": pager,
            "records": posts,
        })

    # -----------------------------
    # New root URL for blog post
    # /<slug> resolves ONLY if slug matches a blog.post record
    # -----------------------------
    # @http.route(['/<model("blog.post"):post>'], type="http", auth="public", website=True, sitemap=False)
    # def blog_post_detail(self, post, **kwargs):
    #     # same access rule as standard
    #     if not post.website_published and not request.env.user.has_group("website.group_website_designer"):
    #         raise NotFound()
    #
    #     # delegate to the standard controller to build the full context
    #     return WebsiteBlog().blog_post(blog=post.blog_id, blog_post=post, **kwargs)
    @http.route(
        ['/<model("blog.post"):post>'],
        type="http",
        auth="public",
        website=True,
        sitemap=True,
    )
    def blog_post_detail(self, post, **kwargs):
        # Same access rule as standard blog controller
        if (not post.website_published and
                not request.env.user.has_group("website.group_website_designer")):
            raise NotFound()

        response = super().blog_post(
            blog=post.blog_id,
            blog_post=post,
            **kwargs
        )
        template_map = {
            "blog": "website_blog.blog_post_complete",
            "daily_tour": "luxboat.daily_tour_detail_tpl",
            "boat_rental": "luxboat.boat_rental_detail_tpl",
            "gallery": "luxboat.gallery_detail_tpl",
        }
        template = template_map.get(post.post_type, "website_blog.blog_post_complete")

        return request.render(template, response.qcontext)
        # -----------------------------
        # 301 redirect old detail URL
        # /blog/<slug> -> /<slug>
        # -----------------------------
        # @http.route([
        #     '/blog/<model("blog.post"):post>',
        #     '/blog/<model("blog.post"):post>/<path:path>',
        # ], type="http", auth="public", website=True, sitemap=False)
        # def blog_post_redirect(self, post, path=None, **kwargs):
        #     target = "/" + slug(post)
        #     if path:
        #         target += "/" + path
        #     return redirect(target, code=301)

        # -----------------------------
        # Custom blog list page
        # -----------------------------

    # We create this URL, but Website editor will add this to Menu.
    @http.route(["/dich-vu-tour-theo-ngay"], type="http", auth="public", website=True, sitemap=True)
    def daily_tour_index(self, **kwargs):
        page = int(kwargs.get("page", 1))
        BlogPost = self._posts_env()
        daily_tour_domain = self._post_domain("daily_tour")

        # Pagination
        step = 10
        total = BlogPost.search_count(daily_tour_domain)
        pager = request.website.pager(
            url="/dich-vu-tour-theo-ngay",
            total=total,
            page=page,
            step=step,
            scope=7,
        )

        daily_tours = BlogPost.search(daily_tour_domain, order="sequence asc, id desc", limit=step, offset=pager["offset"])

        return request.render("luxboat.daily_tour_list_tpl", {
            "pager": pager,
            "records": daily_tours,
        })

    @http.route(["/dich-vu-thue-ca-tau"], type="http", auth="public", website=True, sitemap=True)
    def boat_rental_index(self, **kwargs):
        page = int(kwargs.get("page", 1))
        BlogPost = self._posts_env()
        boat_rental_domain = self._post_domain("boat_rental")

        # Pagination
        step = 10
        total = BlogPost.search_count(boat_rental_domain)
        pager = request.website.pager(
            url="/dich-vu-thue-ca-tau",
            total=total,
            page=page,
            step=step,
            scope=7,
        )

        boat_rentals = BlogPost.search(boat_rental_domain, order="sequence asc, id desc", limit=step, offset=pager["offset"])

        return request.render("luxboat.boat_rental_list_tpl", {
            "pager": pager,
            "records": boat_rentals,
        })

    @http.route(["/gallery"], type="http", auth="public", website=True, sitemap=True)
    def gallery_index(self, **kwargs):
        page = int(kwargs.get("page", 1))
        BlogPost = self._posts_env()
        gallery_domain = self._post_domain("gallery")

        # Pagination
        step = 9
        total = BlogPost.search_count(gallery_domain)
        pager = request.website.pager(
            url="/gallery",
            total=total,
            page=page,
            step=step,
            scope=7,
        )

        galleries = BlogPost.search(gallery_domain, order="sequence asc, id desc", limit=step, offset=pager["offset"])
        return request.render("luxboat.gallery_list_tpl", {
            "pager": pager,
            "records": galleries,
        })

    @http.route(["/ha-long-bay"], type="http", auth="public", website=True, sitemap=True)
    def ha_long_destination_index(self, **kwargs):
        page = int(kwargs.get("page", 1))
        BlogPost = self._posts_env()
        destination_domain = [
            ("website_published", "=", True),
            ("blog_id.website_id", "in", [False, request.website.id]),
            ("post_type", "in", ['boat_rental', 'daily_tour']),
        ]

        # Pagination
        step = 20
        total = BlogPost.search_count(destination_domain)
        pager = request.website.pager(
            url="/ha-long-bay",
            total=total,
            page=page,
            step=step,
            scope=7,
        )

        destinations = BlogPost.search(destination_domain, order="sequence asc, id desc", limit=step, offset=pager["offset"])

        return request.render("luxboat.luxboat_destination_list_tpl", {
            "pager": pager,
            "records": destinations,
        })
