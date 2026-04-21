import logging
from odoo import models
from odoo.http import request

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _match(cls, path):
        try:
            httpreq = getattr(request, "httprequest", None)
            if not httpreq or httpreq.method not in ("GET", "HEAD"):
                return super()._match(path)
            if path.startswith(("/web", "/mail", "/jsonrpc", "/longpolling", "/websocket", "/bus")):
                return super()._match(path)

            # Force default website language only when visitor has not chosen one.
            if not httpreq.cookies.get("frontend_lang") and not path.startswith("/en"):
                request.update_context(lang="vi_VN")
        except Exception as err:
            _logger.debug("Unable to apply default website language for path %s: %s", path, err)

        return super()._match(path)
