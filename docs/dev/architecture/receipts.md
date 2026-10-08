# Receipts and receipt photos

Code: `services/receipts.py`, `services/receipt_images.py`, `routers/receipts.py`; files through
`EncryptedFileStore` (`app/crypto/files.py`). Phone uploads arrive through sync ([sync.md](sync.md)).

## Routes (this computer only)

- `GET/POST /api/local/receipts` (`limit`, `offset`; newest first) and `GET/PATCH/DELETE /api/local/receipts/{id}`.
  A receipt has a `date`, `merchant` (the shop), `total_cents` (≥ 0), and optionally `category_id`,
  `transaction_id` (the matching bank transaction), `tax_deductible`, and `notes` (encrypted). `has_image` says
  whether a photo is attached. Deleting a linked transaction or category just unlinks the receipt.
- `PUT /api/local/receipts/{id}/image`: add or replace the photo. The body is the photo's bytes (not a form
  upload). JPEG, PNG or HEIC, up to **3 MB**. The type comes from the file's first bytes, so a renamed file or a
  wrong `Content-Type` doesn't fool it. Too big: 413 `image_too_large`; not a readable photo: 422 `image_invalid`.
- `GET /api/local/receipts/{id}/image` shows it; `?download=true` saves it as `receipt-<id>.<jpg|png|heic>`,
  never named after the shop.
- `DELETE /api/local/receipts/{id}/image` removes the photo; the receipt details stay.

## What happens to a photo

- **Metadata is stripped first.** For JPEG and PNG only the picture (and its colour profile) is kept; location,
  device and the rest are thrown away before saving. Side effect: the rotation tag goes too, so a sideways
  photo may show sideways.
- **HEIC is saved as is**, so it may still hold a location. It's encrypted and never leaves the computer.
  Fixing this is [issue #34](https://github.com/Redsuperninja/budget-buddy/issues/34).
- **Encrypted** (AES-256-GCM) before it's written to `receipts/` in the data folder, under a random file name
  with no shop, date or amount in it. The plain photo is never written to disk.
- **Deleting a receipt deletes its file.** If the Home Base stops part-way (say a power cut), the worst case is an
  unused encrypted file; at startup, files over an hour old that no receipt points to are removed. Files Budget
  Buddy didn't make are never touched.
- Reading text off the photo (OCR) isn't built yet:
  [issue #33](https://github.com/Redsuperninja/budget-buddy/issues/33).
