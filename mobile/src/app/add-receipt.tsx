import * as Crypto from 'expo-crypto';
import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { ReceiptCamera } from '@/components/receipts/ReceiptCamera';
import { ReceiptDetailsForm } from '@/components/receipts/ReceiptDetailsForm';
import { WaitingReceipts } from '@/components/receipts/WaitingReceipts';
import { BigButton, BodyText, Screen } from '@/components/Screen';
import type { PreparedPhoto } from '@/receipts/photo';
import { addReceipt, clearQueue, listReceipts, queueReadable, removeReceipts } from '@/receipts/receiptQueue';
import type { QueuedReceipt, ReceiptDetails } from '@/receipts/receiptQueue';
import { useSnapshot } from '@/sync/store';

type Step = { name: 'list' } | { name: 'camera' } | { name: 'details'; photo: PreparedPhoto };

export const SAVED_TEXT = "Saved. It will go to your computer the next time you sync on home Wi-Fi.";

/**
 * Add Receipt (roadmap #20): take a photo, add what you know, and it waits on this phone, encrypted,
 * until the next sync sends it home. Lists the receipts still waiting; one your computer turned down
 * shows its reason with Retake and Delete.
 */
export default function AddReceiptScreen() {
  const { snapshot, isSample } = useSnapshot();
  const [step, setStep] = useState<Step>({ name: 'list' });
  const [receipts, setReceipts] = useState<QueuedReceipt[]>([]);
  const [readable, setReadable] = useState(true);
  const [note, setNote] = useState<string | null>(null);
  const [retaking, setRetaking] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setReadable(await queueReadable());
    setReceipts(await listReceipts());
  }, []);

  // Re-read each time the tab is shown: a sync may have sent some.
  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  const categories = isSample ? [] : snapshot.budget.groups.flatMap((g) => g.categories);

  const save = async (photo: PreparedPhoto, details: ReceiptDetails): Promise<string | null> => {
    try {
      await addReceipt(
        {
          ...details,
          client_id: Crypto.randomUUID().toLowerCase(),
          captured_at: new Date().toISOString(),
          width: photo.width,
          height: photo.height,
        },
        photo.jpeg,
      );
    } catch (e) {
      return e instanceof Error ? e.message : "This photo can't be saved. Please take it again.";
    }
    // The new photo is saved; the old one goes too. If that fails it just stays listed to delete.
    if (retaking) await removeReceipts([retaking]).catch(() => undefined);
    setRetaking(null);
    setNote(SAVED_TEXT);
    setStep({ name: 'list' });
    await refresh();
    return null;
  };

  if (step.name === 'camera') {
    return (
      <Screen title="Take a photo">
        <ReceiptCamera
          onTaken={(photo) => setStep({ name: 'details', photo })}
          onCancel={() => setStep({ name: 'list' })}
        />
      </Screen>
    );
  }
  if (step.name === 'details') {
    return (
      <Screen title="About this receipt">
        <ReceiptDetailsForm
          photo={step.photo}
          categories={categories}
          onSave={(details) => save(step.photo, details)}
          onCancel={() => setStep({ name: 'list' })}
        />
      </Screen>
    );
  }
  return (
    <Screen
      title="Add a receipt"
      intro="Snap a photo of a receipt and Budget Buddy will keep it safe until you're home.">
      {note ? <BodyText>{note}</BodyText> : null}
      <BigButton
        label="Take photo"
        disabled={!readable}
        onPress={() => {
          setNote(null);
          setRetaking(null);
          setStep({ name: 'camera' });
        }}
        accessibilityHint="Opens the camera to photograph a receipt"
      />
      <WaitingReceipts
        receipts={receipts}
        readable={readable}
        currency={snapshot.currency}
        onDelete={(r) => void removeReceipts([r.client_id]).then(refresh)}
        onRetake={(r) => {
          setNote(null);
          setRetaking(r.client_id);
          setStep({ name: 'camera' });
        }}
        onClear={() => void clearQueue().then(refresh)}
      />
    </Screen>
  );
}
