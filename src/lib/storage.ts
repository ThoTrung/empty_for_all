import { getStorage, setStorage } from "zmp-sdk/apis";

const KEY = "troxanh_zmini_jwt";

export async function saveJwt(token: string | null): Promise<void> {
  if (token) {
    await setStorage({ data: { [KEY]: token } });
  } else {
    await setStorage({ data: { [KEY]: "" } });
  }
}

export async function loadJwt(): Promise<string | null> {
  try {
    const res = await getStorage({ keys: [KEY] });
    const v = res[KEY];
    if (typeof v === "string" && v.length > 0) {
      return v;
    }
  } catch {
    /* ignore */
  }
  return null;
}
