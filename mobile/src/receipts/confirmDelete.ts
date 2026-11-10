import { Alert } from 'react-native';

/** The question asked before waiting receipts are thrown away (their photos exist only on this phone). */
export function deleteQuestion(count: number | null): { title: string; message: string; action: string } {
  if (count === 1) {
    return { title: 'Delete this receipt?', message: 'The photo will be gone for good.', action: 'Delete' };
  }
  const which = count === null ? 'all the waiting receipts' : `all ${count} waiting receipts`;
  return { title: 'Delete every waiting receipt?', message: `This removes ${which}. The photos will be gone for good.`, action: 'Delete all' };
}

/** Ask first, then run `onConfirm` only if the person chooses to delete. `count` is null when unknown. */
export function confirmDelete(count: number | null, onConfirm: () => void): void {
  const q = deleteQuestion(count);
  Alert.alert(q.title, q.message, [
    { text: 'Keep', style: 'cancel' },
    { text: q.action, style: 'destructive', onPress: onConfirm },
  ]);
}
