export class HttpError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
  ) {
    super(message);
  }
}
export function requireValue(value: unknown, message: string): asserts value {
  if (!value) throw new HttpError(422, "validation_error", message);
}
