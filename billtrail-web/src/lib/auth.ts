const KEY = "billtrail.token";

export const getToken = (): string | null => {
  try { return typeof window === "undefined" ? null : localStorage.getItem(KEY); } catch { return null; }
};
export const setToken = (t: string) => { try { localStorage.setItem(KEY, t); } catch { /* storage blocked */ } };
export const clearToken = () => { try { localStorage.removeItem(KEY); } catch { /* storage blocked */ } };
export const authHeader = (): Record<string, string> => {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
};
