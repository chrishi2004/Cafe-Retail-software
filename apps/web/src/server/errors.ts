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
export function pending(feature: string): never {
  throw new HttpError(
    501,
    "migration_pending",
    `${feature} has not passed native Next.js parity validation.`,
  );
}
