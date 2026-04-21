# -*- coding: utf-8 -*-
import base64
from odoo import http
from odoo.http import request


class LuxboatPopupController(http.Controller):

    @http.route("/luxboat/popup/get", type="json", auth="public", website=True)
    def get_popup(self):
        website = request.website
        path = request.httprequest.path

        popup = request.env["website.popup"].get_first_eligible_popup(website, path)
        if not popup:
            return {"popup": False}

        data = popup.to_public_dict()
        # IMPORTANT: use public image endpoint instead of /web/image
        data["image_url"] = f"/luxboat/popup/image/{popup.id}"
        return {"popup": data}

    @http.route("/luxboat/popup/image/<int:popup_id>", type="http", auth="public", website=True)
    def popup_image(self, popup_id, **kw):
        popup = request.env["website.popup"].sudo().browse(popup_id)
        if not popup.exists() or not popup.cover_image:
            return request.not_found()

        # cover_image is base64 bytes/string in Odoo
        img_b64 = popup.cover_image
        if isinstance(img_b64, str):
            img_b64 = img_b64.encode()

        img = base64.b64decode(img_b64)
        headers = [
            ("Content-Type", "image/png"),  # ok for most; see note below
            ("Cache-Control", "public, max-age=86400"),
        ]
        return request.make_response(img, headers=headers)
