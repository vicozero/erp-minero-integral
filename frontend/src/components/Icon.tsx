import type { ReactNode, SVGProps } from 'react';

export type IconName =
  | 'dashboard'
  | 'requisitions'
  | 'approve'
  | 'warehouse'
  | 'purchases'
  | 'history'
  | 'users'
  | 'audit'
  | 'search'
  | 'sun'
  | 'moon'
  | 'logout'
  | 'key'
  | 'demo'
  | 'box'
  | 'location'
  | 'chart'
  | 'trend'
  | 'alert'
  | 'check'
  | 'clock'
  | 'truck'
  | 'menu'
  | 'close';

const paths: Record<IconName, ReactNode> = {
  dashboard: <><rect x="3" y="3" width="7" height="9" rx="1" /><rect x="14" y="3" width="7" height="5" rx="1" /><rect x="14" y="10" width="7" height="11" rx="1" /><rect x="3" y="14" width="7" height="7" rx="1" /></>,
  requisitions: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5" /><path d="M9 13h7M9 17h7" /></>,
  approve: <><path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" /></>,
  warehouse: <><path d="M3 21V8l9-5 9 5v13" /><path d="M3 21h18" /><path d="M9 21v-7h6v7" /><path d="M3 11h18" /></>,
  purchases: <><path d="M3 7h18v13H3z" /><path d="M8 7V4h8v3" /><path d="M3 12h18" /><path d="M12 12v3" /></>,
  history: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l4 2" /></>,
  users: <><circle cx="9" cy="8" r="3" /><path d="M3 20a6 6 0 0 1 12 0" /><path d="M16 5a3 3 0 0 1 0 6" /><path d="M18 20a5 5 0 0 0-2-4" /></>,
  audit: <><path d="M6 3h9l4 4v14H6z" /><path d="M14 3v5h5" /><path d="M9 13l2 2 4-4" /></>,
  search: <><circle cx="11" cy="11" r="7" /><path d="m20 20-4-4" /></>,
  sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M2 12h2M20 12h2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M19.1 4.9l-1.4 1.4M6.3 17.7l-1.4 1.4" /></>,
  moon: <><path d="M20 14a8 8 0 1 1-10-10 7 7 0 0 0 10 10z" /></>,
  logout: <><path d="M10 17l5-5-5-5" /><path d="M15 12H3" /><path d="M12 3h7a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-7" /></>,
  key: <><circle cx="8" cy="15" r="4" /><path d="m11 12 9-9M17 6l2 2M14 9l2 2" /></>,
  demo: <><path d="M12 3 2 8l10 5 10-5-10-5z" /><path d="M2 12l10 5 10-5" /><path d="M2 16l10 5 10-5" /></>,
  box: <><path d="m12 2 9 5-9 5-9-5 9-5z" /><path d="M3 7v10l9 5 9-5V7" /><path d="M12 12v10" /></>,
  location: <><path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0z" /><circle cx="12" cy="10" r="3" /></>,
  chart: <><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></>,
  trend: <><path d="m3 17 6-6 4 4 8-8" /><path d="M15 7h6v6" /></>,
  alert: <><path d="M12 3 2 20h20L12 3z" /><path d="M12 9v5M12 17h.01" /></>,
  check: <><circle cx="12" cy="12" r="9" /><path d="m8 12 3 3 5-6" /></>,
  clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l4 2" /></>,
  truck: <><path d="M3 6h11v11H3z" /><path d="M14 10h4l3 3v4h-7z" /><circle cx="7" cy="18" r="2" /><circle cx="18" cy="18" r="2" /></>,
  menu: <><path d="M4 6h16M4 12h16M4 18h16" /></>,
  close: <><path d="M6 6l12 12M18 6 6 18" /></>,
};

export function Icon({ name, size = 18, ...rest }: { name: IconName; size?: number } & SVGProps<SVGSVGElement>) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      {paths[name]}
    </svg>
  );
}
