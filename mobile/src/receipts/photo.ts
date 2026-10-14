/**
 * Getting a camera photo ready for the queue (contract §6.1): longest edge at most 1600 px, JPEG quality
 * 0.7. Re-encoding through the image manipulator drops EXIF (location, device details). The camera's own
 * file and the re-encoded one are plain JPEGs, so both are deleted at once: only the bytes are kept, and
 * the queue seals them (`receiptFiles.ts`).
 */

import { Directory, File, Paths } from 'expo-file-system';
import { ImageManipulator, SaveFormat } from 'expo-image-manipulator';

import { MAX_PHOTO_BYTES, photoFits } from './receiptQueue';

export const LONGEST_EDGE = 1600;
const QUALITIES = [0.7, 0.5]; // a second, smaller try in the rare case the first is over 3 MiB

/** The resize that brings the longest edge down to 1600 px, or null if it already fits. */
export function resizeFor(width: number, height: number): { width: number } | { height: number } | null {
  if (Math.max(width, height) <= LONGEST_EDGE) return null;
  return width >= height ? { width: LONGEST_EDGE } : { height: LONGEST_EDGE };
}

function deleteQuietly(uri: string): void {
  try {
    const file = new File(uri);
    if (file.exists) file.delete();
  } catch {
    // Already gone.
  }
}

/**
 * The camera and the image manipulator keep plain JPEGs in their own cache folders until `preparePhoto`
 * deletes them. If the app stopped in between, one could stay; this empties both folders (the app has no
 * other use for them). Run at app start. Never throws.
 */
export function sweepPhotoCaches(): void {
  for (const name of ['Camera', 'ImageManipulator']) {
    try {
      const dir = new Directory(Paths.cache, name);
      if (dir.exists) dir.delete();
    } catch {
      // Nothing there, or already gone.
    }
  }
}

export type PreparedPhoto = { jpeg: Uint8Array; width: number; height: number };

/** Shrink and re-encode the camera's photo; deletes every plain file it touched. Throws if it can't. */
export async function preparePhoto(cameraUri: string, width: number, height: number): Promise<PreparedPhoto> {
  try {
    for (const compress of QUALITIES) {
      const context = ImageManipulator.manipulate(cameraUri);
      const size = resizeFor(width, height);
      if (size) context.resize(size);
      const image = await context.renderAsync();
      const saved = await image.saveAsync({ format: SaveFormat.JPEG, compress });
      try {
        const jpeg = await new File(saved.uri).bytes();
        if (photoFits(jpeg)) return { jpeg, width: saved.width, height: saved.height };
        if (jpeg.length <= MAX_PHOTO_BYTES) break; // not a JPEG at all: a smaller try won't help
      } finally {
        deleteQuietly(saved.uri);
      }
    }
    throw new Error("This photo can't be saved. Please take it again.");
  } finally {
    deleteQuietly(cameraUri);
  }
}
