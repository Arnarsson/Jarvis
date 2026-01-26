const BASE_URL = ''

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text().catch(() => 'Unknown error')
    throw new ApiError(response.status, text)
  }
  // Handle empty responses (204 No Content, or empty body)
  const contentLength = response.headers.get('content-length')
  if (response.status === 204 || contentLength === '0') {
    return {} as T
  }
  const text = await response.text()
  if (!text) return {} as T
  try {
    return JSON.parse(text) as T
  } catch {
    return {} as T
  }
}

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'GET',
    headers: { 'Accept': 'application/json' },
  })
  return handleResponse<T>(response)
}

export async function apiGetText(path: string): Promise<string> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'GET',
  })
  if (!response.ok) {
    throw new ApiError(response.status, await response.text())
  }
  return response.text()
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(`${BASE_URL}${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: body ? JSON.stringify(body) : undefined,
  })
  return handleResponse<T>(response)
}

export { ApiError }
