# -*- coding: utf-8 -*-
from odoo import api, models

class AmountToTextVI(models.AbstractModel):
    _name = 'amount_to_text.vi'
    _description = 'Đọc số tiền tiếng Việt (VND)'

    DIGITS = ["không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín"]
    SCALES = ["", "nghìn", "triệu", "tỷ", "nghìn tỷ", "triệu tỷ"]  # extend if you need hơn nữa

    @api.model
    def vn_amount_to_text(self, amount, currency_name="đồng", use_ngan=False):
        """
        Convert a number to Vietnamese textual money (no decimals).
        - amount: int/float/str; we'll strip separators & 'đ', then round to int.
        - currency_name: e.g., 'đồng' (default)
        - use_ngan: True if you prefer 'ngàn' instead of 'nghìn'
        """
        # 1) Normalize input -> int
        if isinstance(amount, str):
            # remove everything except digits
            import re
            digits = re.sub(r'[^0-9]', '', amount)
            n = int(digits or "0")
        else:
            n = int(round(float(amount or 0)))

        if n == 0:
            return "Không {} chẵn".format(currency_name)

        # Collect non-zero groups (low → high), then read high → low for speech order.
        chunks = []
        i = 0
        n_work = n
        while n_work > 0 and i < len(self.SCALES):
            group = n_work % 1000
            if group:
                chunks.append((group, i))
            n_work //= 1000
            i += 1

        parts = []
        for j, (group, scale_i) in enumerate(reversed(chunks)):
            is_leading = j == 0  # leftmost / largest group — never prefix "không trăm"
            words = self._read_group_3(group, is_leading=is_leading)
            scale = self.SCALES[scale_i]
            if scale:
                words = "{} {}".format(words, "ngàn" if (use_ngan and scale == "nghìn") else scale)
            parts.append(words)

        text = " ".join(parts).strip()

        # Capitalize first letter and add currency tail
        text = text[0].upper() + text[1:]
        if currency_name:
            text = "{} {} chẵn".format(text, currency_name)
        return text

    def _read_group_3(self, num, is_leading=False):
        """
        Read a 3-digit group in VI: ABC
        Rules:
          - hundreds: A > 0 => "<A> trăm"; if A == 0 and (B>0 or C>0) and not the leading group => "không trăm"
          - tens:
              B == 0:
                 if C > 0 => "lẻ <ones>"
              B == 1: "mười <ones(1=>một; 4=>bốn; 5=>lăm; otherwise normal)>"
              B >= 2: "<B> mươi <ones(1=>mốt; 4=>tư; 5=>lăm; 0=>none)>"
        """
        assert 0 <= num <= 999
        a = num // 100
        b = (num % 100) // 10
        c = num % 10

        words = []

        # Hundreds
        if a > 0:
            words.append("{} trăm".format(self.DIGITS[a]))
        elif (b > 0 or c > 0) and not is_leading:
            words.append("không trăm")

        # Tens & ones
        if b == 0:
            if c > 0:
                # 'lẻ' when we have no tens but ones exist
                words.append("lẻ")
                words.append(self._ones_word(c, tens=0))
        elif b == 1:
            words.append("mười")
            if c > 0:
                words.append(self._ones_word(c, tens=1))
        else:
            words.append("{} mươi".format(self.DIGITS[b]))
            if c > 0:
                words.append(self._ones_word(c, tens=b))

        return " ".join(words).strip()

    def _ones_word(self, c, tens):
        """
        Vietnamese special cases for ones after tens:
          - if tens == 0: normal "một, hai, ..." (5 is 'năm')
          - if tens == 1: 1 -> 'một', 4 -> 'bốn', 5 -> 'lăm', else normal
          - if tens >= 2: 1 -> 'mốt', 4 -> 'tư', 5 -> 'lăm', else normal
        """
        if tens == 0:
            return self.DIGITS[c]
        if tens == 1:
            if c == 5:
                return "lăm"
            return self.DIGITS[c]
        # tens >= 2
        if c == 1:
            return "mốt"
        if c == 4:
            return "tư"
        if c == 5:
            return "lăm"
        return self.DIGITS[c]
