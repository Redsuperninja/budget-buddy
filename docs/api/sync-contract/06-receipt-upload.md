Part of the [Sync API contract, v1](../sync-contract.md). Conventions and key names are in §1 there.

## 6. Receipt upload schema

### 6.1 Image transport: inside the encrypted envelope

Receipt photos travel **base64url-encoded inside the encrypted envelope**, not as a multipart upload.

- ADR-0002 requires every sync payload to be encrypted. A multipart file part would need its own encryption
  (its own nonce, its own binding to the request and to the details JSON), which is a second crypto code
  path on both sides. One envelope format for everything is simpler and easier to review.
- The cost is ~33 % base64 overhead plus memory for one batch. The phone keeps that small by **re-encoding
  before queueing** with `expo-image-manipulator`: longest edge ≤ **1600 px**, JPEG quality **0.7**. That
  gives roughly 200–600 KB per receipt, readable for OCR. A typical batch of ≤ 5 receipts is around 1–4 MB.
- **The phone batches by size.** Five photos at the 3 MiB limit would encode to about 20 MiB, over the
  12 MiB body limit (which stays). So a batch is 1–5 items **and** its encoded request stays under
  12 MiB; the phone starts a new batch when the next item would not fit.
- **The phone strips EXIF** (location, device details). Re-encoding through the image manipulator drops
  it; the phone MUST NOT copy metadata across.
- **Server checks before decoding the full image:** decoded data ≤ 3 MiB; starts with the JPEG magic bytes
  `FF D8 FF`; pixel size read from the header (e.g. Pillow `Image.open` without `.load()`, plus
  `Image.MAX_IMAGE_PIXELS`) ≤ 4096 × 4096 and ≤ 16 megapixels. Only then decode. Failures make the item
  `rejected` (`image_too_large` / `image_invalid`).
- The server re-encrypts the image at rest with AES-256-GCM (`EncryptedFileStore`, ADR-0003) and never writes the plain image to disk.

### 6.2 `ReceiptUpload`

```ts
export interface ReceiptUpload {
  client_id: string;              // lowercase UUID v4, generated when the photo is taken; idempotency key
  captured_at: string;            // RFC 3339 with offset or Z, when the photo was taken
  merchant?: string | null;       // <= 100 chars
  total_cents?: number | null;    // integer >= 0
  category_id?: number | null;    // a BudgetCategory.id from the last snapshot
  note?: string | null;           // <= 500 chars
  tax_deductible: boolean;        // default false
  deduction_kind?: 'donation' | 'medical' | 'business' | 'other' | null; // used when tax_deductible
  image: {
    mime: 'image/jpeg';
    width: number;                // px, after downscaling
    height: number;
    data: string;                 // base64url JPEG bytes, EXIF stripped
  };
}
```

Example (image data shortened):

```json
{
  "receipts": [
    {
      "client_id": "3f1c9a0e-8b7d-4c2a-9e51-6d0b7a2f4c18",
      "captured_at": "2026-10-01T12:14:03-05:00",
      "merchant": "Corner Pharmacy",
      "total_cents": 2399,
      "category_id": 4,
      "note": "Allergy meds",
      "tax_deductible": true,
      "deduction_kind": "medical",
      "image": { "mime": "image/jpeg", "width": 1200, "height": 1600, "data": "_9j_4AAQSkZJRgABAQ..." }
    }
  ]
}
```

### 6.3 `ReceiptResult`

```ts
export interface ReceiptResult {
  client_id: string;
  status: 'accepted' | 'duplicate' | 'rejected';
  receipt_id?: number;            // accepted / duplicate: the server's receipt ID
  reason?: 'image_too_large' | 'image_invalid' | 'invalid_field'; // rejected only
  message?: string;               // plain English, rejected only
  warnings?: 'unknown_category'[]; // accepted, with category dropped
}
```

```json
{
  "results": [
    { "client_id": "3f1c9a0e-8b7d-4c2a-9e51-6d0b7a2f4c18", "status": "accepted", "receipt_id": 57 },
    { "client_id": "a0b9...", "status": "duplicate", "receipt_id": 41 },
    { "client_id": "c7d2...", "status": "rejected", "reason": "image_invalid",
      "message": "This photo couldn't be read. Please take it again." }
  ]
}
```

Rules:
- **Idempotency:** `client_id` is unique across the Home Base and is remembered with the phone that sent
  it. If the same phone sends it again, the server stores nothing new and returns `duplicate` with the
  original `receipt_id` (first upload wins, even if the details differ). A retry after a dropped
  connection is always safe. If a different phone sends an ID that exists, that item is `rejected` with
  `invalid_field`, and no `receipt_id` is revealed.
- `category_id` that doesn't exist (e.g. deleted since the last snapshot): accept, set category to none, add
  warning `unknown_category`.
- `tax_deductible: true` without `deduction_kind` → treat as `other`. Turning a `donation` receipt into a
  donation record is server-side logic (#11), not part of this contract.
- Phone: remove `accepted` and `duplicate` items from the queue. Keep `rejected` items, show the message
  on the receipt, and let the user retake or delete it.
