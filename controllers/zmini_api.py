# -*- coding: utf-8 -*-
import json
from odoo import http
from odoo.exceptions import UserError
from odoo.http import request

from odoo.addons.aitilen.tools.portal_phone import normalize_phone_vn_zalo
from odoo.addons.troxanh_zmini.utils.session_token import make_token, read_token
from odoo.addons.troxanh_zmini.utils.zalo_graph import fetch_zalo_verified_phone_number


def _cors_headers():
    icp = request.env['ir.config_parameter'].sudo()
    origin = icp.get_param('troxanh_zmini.cors_allow_origin') or '*'
    return [
        ('Access-Control-Allow-Origin', origin),
        ('Access-Control-Allow-Methods', 'GET, POST, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization'),
        ('Access-Control-Max-Age', '86400'),
    ]


def _json(data, status=200):
    body = json.dumps(data, ensure_ascii=False, default=str)
    headers = [('Content-Type', 'application/json; charset=utf-8')]
    headers.extend(_cors_headers())
    return request.make_response(body, status=status, headers=headers)


def _parse_json():
    try:
        raw = request.httprequest.data
        if not raw:
            return {}
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}


def _web_base_url():
    base = request.env['ir.config_parameter'].sudo().get_param('web.base.url') or ''
    return base.rstrip('/')


def _absolutize_urls(obj, base_url):
    """Prefix relative /web/content paths with web.base.url (for mini app WebView/img)."""
    if not base_url:
        return
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == 'url' and isinstance(val, str) and val.startswith('/'):
                obj[key] = base_url + val
            else:
                _absolutize_urls(val, base_url)
    elif isinstance(obj, list):
        for item in obj:
            _absolutize_urls(item, base_url)


class TroxanhZminiApi(http.Controller):
    @http.route(
        '/troxanh_zmini/api/v1/<path:unused_path>',
        type='http',
        auth='public',
        methods=['OPTIONS'],
        csrf=False,
    )
    def cors_preflight(self, unused_path, **kwargs):
        return request.make_response('', headers=_cors_headers())

    @http.route(
        '/troxanh_zmini/api/v1/contact_config',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def contact_config(self, **kwargs):
        """Same data as /aitilen/contact_config_public + OA id for openChat."""
        icp = request.env['ir.config_parameter'].sudo()
        import re

        phone = (icp.get_param('aitilen.web_phone_number') or '').strip()
        digits = re.sub(r'\D', '', phone) if phone else ''
        zalo_me = ('https://zalo.me/' + normalize_phone_vn_zalo(phone)) if digits else ''
        oa_id = (icp.get_param('troxanh_zmini.zalo_oa_id') or '').strip()
        data = {
            'phone': phone,
            'tel_uri': ('tel:' + phone) if phone else '',
            'zalo_url': zalo_me,
            'facebook_url': (icp.get_param('aitilen.contact_facebook_url') or '').strip(),
            'youtube_url': (icp.get_param('aitilen.contact_youtube_url') or '').strip(),
            'zalo_oa_id': oa_id,
        }
        return _json(data)

    @http.route(
        '/troxanh_zmini/api/v1/empty_rooms',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def empty_rooms(self, **kwargs):
        domain = [
            ('status', 'in', ['will_empty', 'empty']),
            ('website_published', 'in', ['public']),
        ]
        rooms = request.env['aitilen.room'].sudo().search(domain)
        grouped = rooms.get_website_published_room_group_by_area()
        base = _web_base_url()
        _absolutize_urls(grouped, base)
        return _json({'areas': grouped})

    @http.route(
        '/troxanh_zmini/api/v1/room/<int:room_id>',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def room_detail(self, room_id, **kwargs):
        room = request.env['aitilen.room'].sudo().browse(room_id).exists()
        if not room or room.website_published not in ('public_but_not_show_on_empty_list', 'public'):
            return _json({'error': 'not_found'}, status=404)
        info = room.get_website_published_room_info()
        base = _web_base_url()
        _absolutize_urls(info, base)
        return _json(info)

    @http.route(
        '/troxanh_zmini/api/v1/auth/zalo',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def auth_zalo(self, **kwargs):
        """
        Body JSON: {"access_token": "...", "code": "..."} from Zalo getPhoneNumber.
        Returns {"access_token": "<jwt>", "user_type": "tenant"|"guest"}.
        """
        body = _parse_json()
        access_token = (body.get('access_token') or '').strip()
        code = (body.get('code') or '').strip()
        icp = request.env['ir.config_parameter'].sudo()
        secret_key = (icp.get_param('troxanh_zmini.zalo_app_secret') or '').strip()
        jwt_secret = (icp.get_param('troxanh_zmini.jwt_secret') or '').strip()

        if not jwt_secret:
            return _json({'error': 'server_misconfigured', 'detail': 'jwt_secret'}, status=503)
        if not secret_key:
            return _json({'error': 'server_misconfigured', 'detail': 'zalo_app_secret'}, status=503)

        phone = fetch_zalo_verified_phone_number(secret_key, access_token, code)
        if not phone:
            return _json({'error': 'zalo_phone_denied'}, status=401)

        portal = request.env['aitilen.portal.customer.service'].find_portal_rental_user_by_phone(phone)
        if not portal:
            return _json({'user_type': 'guest', 'access_token': None})

        token = make_token(portal.id, jwt_secret)
        return _json({
            'user_type': 'tenant',
            'access_token': token,
            'user': {
                'id': portal.id,
                'name': portal.name,
            },
        })

    def _portal_env_from_bearer(self):
        auth = request.httprequest.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            return None
        raw = auth[7:].strip()
        if not raw:
            return None
        jwt_secret = (request.env['ir.config_parameter'].sudo().get_param('troxanh_zmini.jwt_secret') or '').strip()
        if not jwt_secret:
            return None
        payload = read_token(raw, jwt_secret)
        if not payload:
            return None
        user = request.env['res.users'].sudo().browse(payload['uid']).exists()
        if not user or user._is_public():
            return None
        return request.env(user=user.id)

    @http.route(
        '/troxanh_zmini/api/v1/me',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def me(self, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        user = env.user
        return _json({
            'id': user.id,
            'name': user.name,
            'need_confirm_extend_contract': bool(user.need_confirm_extend_contract),
        })

    @http.route(
        '/troxanh_zmini/api/v1/contracts',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def contracts_list(self, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        svc = env['aitilen.portal.customer.service']
        user = env.user
        out = []
        for c in svc.get_room_contracts_for_portal_user(user):
            out.append(svc.contract_to_miniapp_dict(c))
        return _json({'contracts': out})

    @http.route(
        '/troxanh_zmini/api/v1/invoices',
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
    )
    def invoices_list(self, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        svc = env['aitilen.portal.customer.service']
        user = env.user
        out = [svc.invoice_to_miniapp_dict(inv) for inv in svc.get_contract_invoices_for_portal_user(user)]
        return _json({'invoices': out})

    @http.route(
        '/troxanh_zmini/api/v1/tasks',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def tasks(self, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        svc = env['aitilen.portal.customer.service']
        user = env.user
        if request.httprequest.method == 'GET':
            out = [svc.task_to_miniapp_dict(t) for t in svc.get_tasks_for_portal_user(user)]
            return _json({'tasks': out})
        body = _parse_json()
        try:
            svc.portal_create_task(user, body.get('name'), body.get('note'))
        except UserError as e:
            return _json({'error': 'user_error', 'message': str(e)}, status=400)
        return _json({'ok': True})

    @http.route(
        '/troxanh_zmini/api/v1/vehicles',
        type='http',
        auth='public',
        methods=['GET', 'POST'],
        csrf=False,
    )
    def vehicles(self, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        svc = env['aitilen.portal.customer.service']
        user = env.user
        if request.httprequest.method == 'GET':
            mine = [svc.vehicle_to_miniapp_dict(v) for v in svc.get_vehicles_for_portal_user(user)]
            grouped = svc.get_grouped_house_vehicles_for_portal()
            house_rows = []
            for room_number, veh_list in sorted(grouped.items(), key=lambda x: (x[0] or '')):
                for v in veh_list:
                    house_rows.append({
                        'room_number': room_number,
                        **svc.vehicle_to_miniapp_dict(v),
                    })
            return _json({'vehicles': mine, 'house_vehicles': house_rows})
        body = _parse_json()
        try:
            svc.portal_create_vehicle(
                user,
                body.get('name'),
                body.get('type'),
                body.get('license_plates'),
            )
        except UserError as e:
            return _json({'error': 'user_error', 'message': str(e)}, status=400)
        return _json({'ok': True})

    @http.route(
        '/troxanh_zmini/api/v1/vehicles/<int:vehicle_id>/archive',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def vehicle_archive(self, vehicle_id, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        svc = env['aitilen.portal.customer.service']
        ok = svc.portal_archive_vehicle(env.user, vehicle_id)
        return _json({'ok': bool(ok)})

    @http.route(
        '/troxanh_zmini/api/v1/contracts/confirm_extend',
        type='http',
        auth='public',
        methods=['POST'],
        csrf=False,
    )
    def contract_confirm_extend(self, **kwargs):
        env = self._portal_env_from_bearer()
        if not env:
            return _json({'error': 'unauthorized'}, status=401)
        body = _parse_json()
        cid = body.get('contract_id')
        svc = env['aitilen.portal.customer.service']
        ok = svc.portal_confirm_extend(env.user, cid)
        return _json({'ok': bool(ok)})
