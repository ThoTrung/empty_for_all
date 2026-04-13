import { useAtomValue } from "jotai";
import { useEffect, useState } from "react";
import { Box, Header, List, Page, Spinner, Text } from "zmp-ui";
import { useNavigate } from "react-router-dom";

import { apiGet } from "@/api/client";
import type { TaskItem } from "@/api/types";
import { jwtAtom } from "@/state/authAtoms";

type Resp = { tasks: TaskItem[] };

function ProfileTasksPage() {
  const navigate = useNavigate();
  const jwt = useAtomValue(jwtAtom);
  const [data, setData] = useState<TaskItem[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!jwt) {
      setErr("Chưa đăng nhập.");
      setLoading(false);
      return;
    }
    apiGet<Resp>("/troxanh_zmini/api/v1/tasks", jwt)
      .then((r) => setData(r.tasks))
      .catch(() => setErr("Không tải được yêu cầu."))
      .finally(() => setLoading(false));
  }, [jwt]);

  return (
    <Page>
      <Header
        title="Yêu cầu"
        showBackIcon
        onBackClick={() => navigate(-1)}
      />
      <div className="p-4 pt-16 zmini-page-pad">
        {loading && (
          <Box className="flex justify-center py-10">
            <Spinner />
          </Box>
        )}
        {err && <Text className="text-danger">{err}</Text>}
        {data && data.length === 0 && (
          <Text className="text-gray-500 py-4">Chưa có yêu cầu.</Text>
        )}
        <List>
          {data?.map((t) => (
            <List.Item key={t.id}>
              <div className="space-y-1">
                <Text className="font-medium">{t.name}</Text>
                {t.stage_name && (
                  <Text size="xSmall" className="text-gray-500">
                    {t.stage_name}
                  </Text>
                )}
                {t.note_html && (
                  <div
                    className="text-sm"
                    dangerouslySetInnerHTML={{ __html: t.note_html }}
                  />
                )}
              </div>
            </List.Item>
          ))}
        </List>
      </div>
    </Page>
  );
}

export default ProfileTasksPage;
