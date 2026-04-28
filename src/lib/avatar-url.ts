const ALLOWED_AVATAR_HOST_PATTERNS = [
  /(^|\.)cdninstagram\.com$/i,
  /^scontent-[a-z0-9-]+\.cdninstagram\.com$/i,
  /(^|\.)fbcdn\.net$/i,
  /(^|\.)tiktokcdn\.com$/i,
  /(^|\.)tiktokcdn-us\.com$/i,
  /(^|\.)tiktokcdn-eu\.com$/i,
  /^p\d+-common-sign\.tiktokcdn(?:-[a-z]+)?\.com$/i,
  /^p\d+-sign\.tiktokcdn(?:-[a-z]+)?\.com$/i,
  /^p\d+-[^.]+\.tiktokcdn(?:-[a-z]+)?\.com$/i,
  /^yt3\.ggpht\.com$/i,
  /^yt3\.googleusercontent\.com$/i,
]

export function proxiedAvatarUrl(url: string | null | undefined): string | null {
  if (!url) return null
  let parsed: URL
  try {
    parsed = new URL(url)
  } catch {
    return null
  }

  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return null
  if (!isAllowedAvatarHost(parsed.hostname)) return url
  return `/api/avatar?url=${encodeURIComponent(url)}`
}

export function isAllowedAvatarHost(hostname: string): boolean {
  return ALLOWED_AVATAR_HOST_PATTERNS.some((pattern) => pattern.test(hostname))
}
