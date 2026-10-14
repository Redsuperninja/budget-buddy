import { CameraView, useCameraPermissions } from 'expo-camera';
import { useRef, useState } from 'react';
import { Text, View } from 'react-native';

import { BigButton, BodyText } from '@/components/Screen';
import { preparePhoto } from '@/receipts/photo';
import type { PreparedPhoto } from '@/receipts/photo';
import { useTheme } from '@/theme';

export const CAMERA_DENIED =
  'Budget Buddy needs the camera to photograph receipts. Allow the camera in your phone settings, then try again.';
export const PHOTO_FAILED = "That photo didn't work. Please try again.";

/** Take one receipt photo, shrunk and cleaned for the queue (`receipts/photo.ts`). */
export function ReceiptCamera({ onTaken, onCancel }: { onTaken: (photo: PreparedPhoto) => void; onCancel: () => void }) {
  const t = useTheme();
  const [permission, requestPermission] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  if (!permission?.granted) {
    return (
      <>
        <BodyText>Budget Buddy uses the camera only to photograph receipts. Photos stay on this phone until you sync.</BodyText>
        {problem ? <Text accessibilityRole="alert" style={{ color: t.colors.negative, fontSize: t.fontSizes.body }}>{problem}</Text> : null}
        <BigButton
          label="Allow the camera"
          onPress={() =>
            void requestPermission().then((r) => {
              if (!r.granted) setProblem(CAMERA_DENIED);
            })
          }
        />
        <BigButton label="Cancel" onPress={onCancel} />
      </>
    );
  }

  const take = async () => {
    if (busy || !camera.current) return;
    setBusy(true);
    setProblem(null);
    try {
      // exif:false only keeps EXIF out of JS; the re-encode in preparePhoto is what strips it from the photo.
      const shot = await camera.current.takePictureAsync({ exif: false, skipProcessing: false });
      onTaken(await preparePhoto(shot.uri, shot.width, shot.height));
    } catch {
      setProblem(PHOTO_FAILED);
      setBusy(false);
    }
  };

  return (
    <>
      <View style={{ height: 420, borderRadius: t.radius.md, overflow: 'hidden' }}>
        <CameraView ref={camera} style={{ flex: 1 }} facing="back" />
      </View>
      <BodyText muted>Fit the whole receipt on the screen, in good light.</BodyText>
      {problem ? <Text accessibilityRole="alert" style={{ color: t.colors.negative, fontSize: t.fontSizes.body }}>{problem}</Text> : null}
      <BigButton label={busy ? 'Getting the photo ready...' : 'Take photo'} disabled={busy} onPress={() => void take()} />
      <BigButton label="Cancel" disabled={busy} onPress={onCancel} />
    </>
  );
}
