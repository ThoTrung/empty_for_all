import { getSystemInfo } from "zmp-sdk";
import {
  AnimationRoutes,
  App,
  Route,
  SnackbarProvider,
  ZMPRouter,
} from "zmp-ui";
import { AppProps } from "zmp-ui/app";

import MainShell from "@/components/MainShell";
import HomePage from "@/pages/home";
import NewsPage from "@/pages/news";
import ProfilePage from "@/pages/profile";
import ProfileContractsPage from "@/pages/profile-contracts";
import ProfileInvoicesPage from "@/pages/profile-invoices";
import ProfileTasksPage from "@/pages/profile-tasks";
import ProfileVehiclesPage from "@/pages/profile-vehicles";
import RoomDetailPage from "@/pages/room-detail";
import RoomsPage from "@/pages/rooms";

const Layout = () => {
  return (
    <App theme={getSystemInfo().zaloTheme as AppProps["theme"]}>
      <SnackbarProvider>
        <ZMPRouter>
          <AnimationRoutes>
            <Route path="/room/:id" element={<RoomDetailPage />} />
            <Route
              path="/profile/contracts"
              element={<ProfileContractsPage />}
            />
            <Route
              path="/profile/invoices"
              element={<ProfileInvoicesPage />}
            />
            <Route path="/profile/tasks" element={<ProfileTasksPage />} />
            <Route
              path="/profile/vehicles"
              element={<ProfileVehiclesPage />}
            />
            <Route path="/" element={<MainShell />}>
              <Route index element={<HomePage />} />
              <Route path="rooms" element={<RoomsPage />} />
              <Route path="news" element={<NewsPage />} />
              <Route path="profile" element={<ProfilePage />} />
            </Route>
          </AnimationRoutes>
        </ZMPRouter>
      </SnackbarProvider>
    </App>
  );
};
export default Layout;
