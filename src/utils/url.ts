// Join a site-relative path with the configured Astro `base`,
// handling BASE_URL values with or without a trailing slash.
export function withBase(path: string): string {
  const base = import.meta.env.BASE_URL;
  const prefix = base.endsWith('/') ? base : `${base}/`;
  return `${prefix}${path.replace(/^\//, '')}`;
}
