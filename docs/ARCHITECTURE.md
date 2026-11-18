# Web architecture

Kalpvriksh is one Next.js application deployed from `apps/web`.

```text
Staff browser / customer phone
              |
              v
       Vercel HTTPS origin
              |
       +------+------+
       |             |
   React UI      /api Route Handler
                     |
              TypeScript services
                     |
                MongoDB Atlas
```

All browser API requests are same-origin. Public Café QR capabilities are
short-lived and cannot issue invoices, record payment or modify authoritative
stock. Authenticated roles and venture/branch scope are enforced server-side.

The product requires internet access. Offline Local Hub synchronization is not
part of this architecture; it is preserved only in the private archive repository.
