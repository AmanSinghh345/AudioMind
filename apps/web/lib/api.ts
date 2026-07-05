export type ApiOptions = {
  baseUrl?: string;
  apiKey?: string;
};

export type ApiRequestOptions = RequestInit & {
  retryWithApiKey?: (message: string) => string;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const DEFAULT_API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ||
  (process.env.NODE_ENV === "development" ? "http://localhost:8080" : "");

async function readError(response: Response) {
  const contentType = response.headers.get("content-type") || "";
  if (contentType.includes("application/json")) {
    const body = await response.json().catch(() => null);
    if (typeof body?.detail === "string") return body.detail;
    if (body?.detail) return JSON.stringify(body.detail);
  }
  return (await response.text().catch(() => "")) || response.statusText || "Request failed";
}

export class ApiClient {
  baseUrl: string;
  apiKey: string;

  constructor(options: ApiOptions = {}) {
    this.baseUrl = (options.baseUrl || DEFAULT_API_BASE).replace(/\/$/, "");
    this.apiKey = options.apiKey || "";
  }

  audioUrl(fileName: string) {
    return `${this.baseUrl}/audio/${encodeURIComponent(fileName)}`;
  }

  async request<T>(path: string, options: ApiRequestOptions = {}): Promise<T> {
    if (!this.baseUrl) {
      throw new ApiError("API URL is not configured.", 0);
    }

    const headers = new Headers(options.headers);
    if (this.apiKey) headers.set("X-API-Key", this.apiKey);

    const response = await fetch(`${this.baseUrl}${path}`, { ...options, headers });
    if (response.status === 401 && options.retryWithApiKey) {
      const nextKey = options.retryWithApiKey("Enter AI Audiobook API key");
      if (nextKey) {
        this.apiKey = nextKey;
        headers.set("X-API-Key", nextKey);
        const retry = await fetch(`${this.baseUrl}${path}`, { ...options, headers });
        if (!retry.ok) throw new ApiError(await readError(retry), retry.status);
        return retry.status === 204 ? (null as T) : retry.json();
      }
    }

    if (!response.ok) throw new ApiError(await readError(response), response.status);
    return response.status === 204 ? (null as T) : response.json();
  }
}
