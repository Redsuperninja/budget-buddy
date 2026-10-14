import { useMemo, useState } from 'react';
import { Image, Switch, Text, View } from 'react-native';
import { encodeBase64 } from 'tweetnacl-util';

import { ChoiceChips, TextField } from '@/components/Field';
import { BigButton, BodyText } from '@/components/Screen';
import type { PreparedPhoto } from '@/receipts/photo';
import { DEDUCTION_KINDS, EMPTY_FIELDS, MERCHANT_MAX, NOTE_MAX, readFields } from '@/receipts/receiptForm';
import type { ReceiptFields } from '@/receipts/receiptForm';
import type { ReceiptDetails } from '@/receipts/receiptQueue';
import type { BudgetCategory } from '@/sync/snapshot';
import { useTheme } from '@/theme';

/**
 * What you know about the receipt, all optional: store, total, category (from your last sync), a note,
 * and whether it's tax deductible (and what kind). The photo is shown from memory only.
 */
export function ReceiptDetailsForm({
  photo,
  categories,
  onSave,
  onCancel,
}: {
  photo: PreparedPhoto;
  categories: BudgetCategory[];
  onSave: (details: ReceiptDetails) => Promise<string | null>;
  onCancel: () => void;
}) {
  const t = useTheme();
  const [f, setF] = useState<ReceiptFields>(EMPTY_FIELDS);
  const [problem, setProblem] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const set = (change: Partial<ReceiptFields>) => setF((old) => ({ ...old, ...change }));
  // Built once per photo, not on every keystroke (it's a few MB); memory only.
  const preview = useMemo(() => `data:image/jpeg;base64,${encodeBase64(photo.jpeg)}`, [photo]);

  const save = async () => {
    const read = readFields(f);
    if ('problem' in read) return setProblem(read.problem);
    setSaving(true);
    const failed = await onSave(read.details);
    if (failed) {
      setProblem(failed);
      setSaving(false);
    }
  };

  return (
    <>
      <Image
        accessibilityLabel="The receipt photo"
        source={{ uri: preview }}
        style={{ width: '100%', aspectRatio: photo.width / photo.height, borderRadius: t.radius.md }}
        resizeMode="contain"
      />
      <BodyText muted>Fill in what you know; you can leave any of it empty.</BodyText>
      <TextField label="Store" value={f.merchant} onChangeText={(merchant) => set({ merchant })} maxLength={MERCHANT_MAX} />
      <TextField label="Total" value={f.total} onChangeText={(total) => set({ total })} keyboardType="decimal-pad" placeholder="23.99" />
      {categories.length > 0 ? (
        <View style={{ gap: t.spacing.xs }}>
          <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>Category</Text>
          <ChoiceChips
            choices={categories.map((c) => ({ value: c.id, label: c.name }))}
            selected={f.categoryId}
            onChoose={(categoryId) => set({ categoryId: f.categoryId === categoryId ? null : categoryId })}
          />
        </View>
      ) : null}
      <TextField label="Note" value={f.note} onChangeText={(note) => set({ note })} maxLength={NOTE_MAX} multiline />
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: t.minTouchSize }}>
        <Text style={{ fontSize: t.fontSizes.body, color: t.colors.text }}>Tax deductible</Text>
        <Switch
          accessibilityLabel="Tax deductible"
          value={f.taxDeductible}
          onValueChange={(taxDeductible) => set({ taxDeductible })}
        />
      </View>
      {f.taxDeductible ? (
        <ChoiceChips
          choices={DEDUCTION_KINDS.map((d) => ({ value: d.kind, label: d.label }))}
          selected={f.deductionKind}
          onChoose={(deductionKind) => set({ deductionKind })}
        />
      ) : null}
      {problem ? (
        <Text accessibilityRole="alert" style={{ color: t.colors.negative, fontSize: t.fontSizes.body }}>
          {problem}
        </Text>
      ) : null}
      <BigButton label={saving ? 'Saving...' : 'Save receipt'} disabled={saving} onPress={() => void save()} />
      <BigButton label="Cancel" disabled={saving} onPress={onCancel} />
    </>
  );
}
