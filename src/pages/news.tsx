import { Box, Button, Page, Text } from "zmp-ui";
import { openWebview } from "zmp-sdk/apis";

const NEWS_URL =
  import.meta.env.VITE_WEBSITE_NEWS_URL ||
  import.meta.env.VITE_WEBSITE_BASE_URL ||
  "";

function NewsPage() {
  return (
    <Page className="bg-background">
      <div className="p-4 space-y-4">
        <Text.Title size="large">Tin tức</Text.Title>
        <Text className="text-gray-600 dark:text-gray-300">
          Nội dung tin tức đang được hiển thị trên website. Bạn có thể mở trang
          tin trong trình duyệt Zalo (không dùng WebView toàn màn hình cho toàn
          app — chỉ khi bạn chọn mở tin).
        </Text>
        {NEWS_URL ? (
          <Button
            variant="primary"
            fullWidth
            onClick={() =>
              openWebview({
                url: NEWS_URL,
              })
            }
          >
            Mở trang tin trên website
          </Button>
        ) : (
          <Box className="rounded-lg bg-section p-3 text-sm">
            Thiết lập biến <code className="text-xs">VITE_WEBSITE_NEWS_URL</code>{" "}
            trong file môi trường để nút mở tin hoạt động.
          </Box>
        )}
      </div>
    </Page>
  );
}

export default NewsPage;
