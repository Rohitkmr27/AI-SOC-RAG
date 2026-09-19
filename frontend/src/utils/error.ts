import { AxiosError } from 'axios';

/**
 * Format API error into a clean, human-readable SOC message without exposing stack traces.
 */
export function formatApiError(err: unknown, fallbackMessage = 'An unexpected error occurred'): string {
  if (!err) return fallbackMessage;

  if (err instanceof AxiosError) {
    if (err.response) {
      const status = err.response.status;
      const data = err.response.data;

      // FastAPI detail field
      if (data && typeof data === 'object' && 'detail' in data) {
        const detail = (data as { detail: unknown }).detail;
        if (typeof detail === 'string') return detail;
        if (Array.isArray(detail)) {
          // Pydantic validation error array
          return detail.map((d: unknown) => (typeof d === 'object' && d !== null && 'msg' in d ? String((d as Record<string, unknown>).msg) : JSON.stringify(d))).join(', ');
        }
      }

      switch (status) {
        case 400:
          return 'Bad Request: The submitted alert or correlation query is invalid.';
        case 404:
          return 'Resource Not Found: The requested alert, incident, or endpoint does not exist.';
        case 422:
          return 'Validation Error: Request parameters do not match backend schema.';
        case 500:
          return 'Internal Server Error: Backend encountered an error while processing request.';
        case 503:
          return 'Service Unavailable: Backend generation or trained model is currently unavailable.';
        default:
          return `Backend returned HTTP ${status}: ${err.message}`;
      }
    } else if (err.request) {
      return 'Unable to connect to AI SOC backend. Please verify the backend service is running at ' + (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000');
    }
    return err.message;
  }

  if (err instanceof Error) {
    return err.message;
  }

  return String(err);
}
