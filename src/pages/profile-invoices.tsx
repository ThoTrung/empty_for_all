import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Box, Header, List, Page, Spinner, Text } from "zmp-ui";
import { useNavigate } from "react-router-dom";

import { apiGet } from "@/api/client";
import type { InvoiceItem } from "@/api/types";
import { jwtAtom } from "@/state/authAtoms";

type Resp = { invoices: InvoiceItem[] };

function ProfileInvoicesPage() {
  const navigate = useNavigate();
  const jwt = useAtomValue(jwtAtom);
  const [data, setData] = useState<InvoiceItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!jwt) {
      setErr("Chưa đăng nhập.");
      setLoading(false);
      return;
    }
    apiGet<Resp>("/troxanh_zmini/api/v1/invoices", jwt)
      .then((r) => setData(r.invoices))
      .catch(() => setErr("Không tải được hóa đơn."))
      .finally(() => setLoading(false));
  }, [jwt]);

  return (
    <Page>
      <Header
        title="Hóa đơn"
        showBackIcon
        onBackClick={() => navigate(-1)}
      />
      <div className="p-4 pt-16 space-y-4 zmini-page-pad">
        {loading && (
          <Box className="flex justify-center py-10">
            <Spinner />
          </Box>
        )}
        {err && <Text className="text-danger">{err}</Text>}
        {data && data.length === 0 && (
          <Text className="text-gray-500">Không có hóa đơn.</Text>
        )}
        {data?.map((inv) => (
          <Box
            key={inv.id}
            className="rounded-xl bg-section p-3 space-y-2 border border-black/5"
          >
            <div className="flex justify-between gap-2">
              <Text className="font-medium">{inv.name}</Text>
              <Text size="small" className="text-primary">
                {inv.payment_label}
              </Text>
            </div>
            {inv.bank_qr_base64 && (
              <img
                src={`data:image/png;base64,${inv.bank_qr_base64}`}
                alt="QR"
                className="w-40 h-40 mx-auto"
              />
            )}
            {(inv.my_bank_name || inv.my_bank_account_no) && (
              <Text size="xSmall" className="text-center">
                {inv.my_bank_name}
                <br />
                {inv.my_bank_account_no}
                <br />
                {inv.my_bank_account_name}
              </Text>
            )}
            {inv.auto_note_html && (
              <div
                className="text-sm max-w-none"
                dangerouslySetInnerHTML={{ __html: inv.auto_note_html }}
              />
            )}
            <Text size="xSmall">
              Đã TT: {inv.total_paid?.toLocaleString("vi-VN")} · Còn:{" "}
              <span className="text-danger font-medium">
                {inv.total_remain?.toLocaleString("vi-VN")}
              </span>
            </Text>
          </Box>
        ))}
      </div>
    </Page>
  );
}

export default ProfileInvoicesPage;
