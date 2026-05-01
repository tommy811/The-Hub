import { NextResponse } from "next/server"
import { isAllowedAvatarHost } from "@/lib/avatar-url"

export const runtime = "nodejs"
export const dynamic = "force-dynamic"

export async function GET(request: Request) {
  const rawUrl = new URL(request.url).searchParams.get("url")
  if (!rawUrl) {
    return new NextResponse("Missing url", { status: 400 })
  }

  let parsed: URL
  try {
    parsed = new URL(rawUrl)
  } catch {
    return new NextResponse("Invalid url", { status: 400 })
  }

  if ((parsed.protocol !== "https:" && parsed.protocol !== "http:") || !isAllowedAvatarHost(parsed.hostname)) {
    return new NextResponse("Disallowed avatar host", { status: 403 })
  }

  const upstream = await fetch(parsed.toString(), {
    headers: {
      "user-agent": "Mozilla/5.0 TheHubAvatarProxy/1.0",
      accept: "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
    },
    redirect: "follow",
    cache: "no-store",
  })

  if (!upstream.ok || !upstream.body) {
    return new NextResponse("Avatar fetch failed", { status: 502 })
  }

  const contentType = upstream.headers.get("content-type") ?? "image/jpeg"
  if (!contentType.startsWith("image/")) {
    return new NextResponse("Upstream did not return an image", { status: 502 })
  }

  return new NextResponse(upstream.body, {
    status: 200,
    headers: {
      "content-type": contentType,
      "cache-control": "public, max-age=3600, stale-while-revalidate=86400",
    },
  })
}
