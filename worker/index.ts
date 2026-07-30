/** Cloudflare Worker entry point for the vinext-starter template. */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  ZOOVISION_EDGE_AUTH_ENABLED?: string;
  ZOOVISION_EDGE_AUTH_USERNAME?: string;
  ZOOVISION_EDGE_AUTH_PASSWORD?: string;
  ZOOVISION_API_ORIGIN?: string;
  ZOOVISION_PROXY_SHARED_SECRET?: string;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

function enabled(value: string | undefined): boolean {
  return value?.trim().toLowerCase() === "true";
}

async function digest(value: string): Promise<ArrayBuffer> {
  return crypto.subtle.digest("SHA-256", new TextEncoder().encode(value));
}

function equalDigest(left: ArrayBuffer, right: ArrayBuffer): boolean {
  const leftBytes = new Uint8Array(left);
  const rightBytes = new Uint8Array(right);
  if (leftBytes.byteLength !== rightBytes.byteLength) return false;

  let difference = 0;
  for (let index = 0; index < leftBytes.byteLength; index += 1) {
    difference |= leftBytes[index] ^ rightBytes[index];
  }
  return difference === 0;
}

async function hasValidBrowserCredentials(request: Request, env: Env): Promise<boolean> {
  const username = env.ZOOVISION_EDGE_AUTH_USERNAME;
  const password = env.ZOOVISION_EDGE_AUTH_PASSWORD;
  if (!username || !password) return false;

  const authorization = request.headers.get("authorization");
  if (!authorization?.startsWith("Basic ")) return false;

  try {
    const decoded = atob(authorization.slice("Basic ".length));
    const separator = decoded.indexOf(":");
    if (separator < 0) return false;

    const supplied = `${decoded.slice(0, separator)}:${decoded.slice(separator + 1)}`;
    const expected = `${username}:${password}`;
    return equalDigest(await digest(supplied), await digest(expected));
  } catch {
    return false;
  }
}

function loginRequired(): Response {
  return new Response("Authentication required.", {
    status: 401,
    headers: {
      "cache-control": "no-store",
      "content-type": "text/plain; charset=utf-8",
      "www-authenticate": 'Basic realm="ZooVision staff", charset="UTF-8"',
    },
  });
}

function configurationUnavailable(): Response {
  return new Response("ZooVision deployment configuration is incomplete.", {
    status: 503,
    headers: {
      "cache-control": "no-store",
      "content-type": "text/plain; charset=utf-8",
    },
  });
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const edgeAuthEnabled = enabled(env.ZOOVISION_EDGE_AUTH_ENABLED);

    if (edgeAuthEnabled) {
      if (!env.ZOOVISION_EDGE_AUTH_USERNAME || !env.ZOOVISION_EDGE_AUTH_PASSWORD) {
        return configurationUnavailable();
      }
      if (!(await hasValidBrowserCredentials(request, env))) {
        return loginRequired();
      }
    }

    if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/media/")) {
      if (!env.ZOOVISION_API_ORIGIN || !env.ZOOVISION_PROXY_SHARED_SECRET) {
        return configurationUnavailable();
      }
      const upstream = new URL(`${url.pathname}${url.search}`, env.ZOOVISION_API_ORIGIN);
      const headers = new Headers(request.headers);
      headers.delete("authorization");
      headers.delete("host");
      headers.delete("x-zoovision-proxy-secret");
      headers.set("x-zoovision-proxy-secret", env.ZOOVISION_PROXY_SHARED_SECRET);
      return fetch(new Request(upstream, { method: request.method, headers, body: request.body }));
    }

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;
