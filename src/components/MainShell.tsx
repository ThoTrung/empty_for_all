import { BottomNavigation, Icon } from "zmp-ui";
import { Outlet, useLocation } from "react-router-dom";

const TAB_KEYS = ["/", "/rooms", "/news", "/profile"] as const;

function pathToKey(pathname: string): string {
  if (pathname === "/") return "home";
  if (pathname === "/rooms") return "rooms";
  if (pathname === "/news") return "news";
  if (pathname === "/profile") return "profile";
  return "home";
}

function MainShell() {
  const { pathname } = useLocation();
  const showTabs = TAB_KEYS.includes(pathname as (typeof TAB_KEYS)[number]);

  return (
    <>
      <Outlet />
      {showTabs && (
        <BottomNavigation
          fixed
          activeKey={pathToKey(pathname)}
          className="z-20"
        >
          <BottomNavigation.Item
            key="home"
            id="tab-home"
            itemKey="home"
            label="Trang chủ"
            linkTo="/"
            icon={<Icon icon="zi-home" />}
            activeIcon={<Icon icon="zi-home" />}
          />
          <BottomNavigation.Item
            key="rooms"
            id="tab-rooms"
            itemKey="rooms"
            label="Phòng trống"
            linkTo="/rooms"
            icon={<Icon icon="zi-list" />}
          />
          <BottomNavigation.Item
            key="news"
            id="tab-news"
            itemKey="news"
            label="Tin tức"
            linkTo="/news"
            icon={<Icon icon="zi-chat" />}
          />
          <BottomNavigation.Item
            key="profile"
            id="tab-profile"
            itemKey="profile"
            label="Cá nhân"
            linkTo="/profile"
            icon={<Icon icon="zi-user" />}
          />
        </BottomNavigation>
      )}
    </>
  );
}

export default MainShell;
