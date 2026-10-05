import Constants from 'expo-constants';
import { CameraView, useCameraPermissions } from 'expo-camera';
import * as Device from 'expo-device';
import { useCallback, useRef, useState } from 'react';
import { Platform, StyleSheet, Text, TextInput, View } from 'react-native';

import { BigButton, BodyText, Card, Screen } from '@/components/Screen';
import { loadCredentials, saveCredentials } from '@/sync/credentials';
import { PairError, PAIR_MESSAGES } from '@/sync/pairErrors';
import { pairWithComputer } from '@/sync/pairClient';
import { parsePairingPayload } from '@/sync/pairingQr';
import { useTheme } from '@/theme';

type Step =
  | { name: 'start' }
  | { name: 'scanning' }
  | { name: 'typing' }
  | { name: 'working' }
  | { name: 'confirm'; text: string }
  | { name: 'done'; computer: string }
  | { name: 'error'; message: string };

export const DIFFERENT_COMPUTER_QUESTION =
  'This is a different computer than the one you connected before. Connect to this one instead?';

const nowSeconds = () => Math.floor(Date.now() / 1000);

export default function PairScreen() {
  const t = useTheme();
  const [permission, requestPermission] = useCameraPermissions();
  const [step, setStep] = useState<Step>({ name: 'start' });
  const [typed, setTyped] = useState('');
  const [phoneName, setPhoneName] = useState(
    (Device.modelName || 'My phone').slice(0, 50),
  );
  const busy = useRef(false); // the camera reports the same code many times

  const pair = useCallback(
    async (text: string, confirmed = false) => {
      if (busy.current) return;
      busy.current = true;
      setStep({ name: 'working' });
      try {
        const qr = parsePairingPayload(text.trim(), nowSeconds());
        const existing = await loadCredentials();
        if (existing && existing.server_id !== qr.server_id && !confirmed) {
          setStep({ name: 'confirm', text });
          return;
        }
        const creds = await pairWithComputer(qr, {
          deviceName: phoneName.trim().slice(0, 50) || 'My phone',
          platform: Platform.OS === 'ios' ? 'ios' : 'android',
          appVersion: Constants.expoConfig?.version ?? '1.0.0',
        });
        await saveCredentials(creds); // only now, after the whole pairing worked
        setStep({ name: 'done', computer: creds.server_name });
      } catch (e) {
        setStep({
          name: 'error',
          message: e instanceof PairError ? e.message : PAIR_MESSAGES.something_wrong,
        });
      } finally {
        busy.current = false;
      }
    },
    [phoneName],
  );

  const canScan = Platform.OS !== 'web'; // web scanning would load code from the internet

  const startScan = async () => {
    if (!permission?.granted) {
      const result = await requestPermission();
      if (!result.granted) {
        setStep({
          name: 'error',
          message:
            'Budget Buddy needs the camera to scan the code. Allow the camera in your phone settings, or type the code instead.',
        });
        return;
      }
    }
    setStep({ name: 'scanning' });
  };

  const inputStyle = {
    minHeight: t.minTouchSize,
    borderRadius: t.radius.md,
    borderWidth: StyleSheet.hairlineWidth,
    borderColor: t.colors.border,
    backgroundColor: t.colors.surface,
    color: t.colors.text,
    fontSize: t.fontSizes.body,
    padding: t.spacing.md,
  };

  return (
    <Screen
      title="Connect to your computer"
      intro="On your computer, open Budget Buddy and click Pair a phone. Then scan the code here. Make sure your phone is on home Wi-Fi.">
      {step.name === 'start' || step.name === 'error' ? (
        <>
          {step.name === 'error' ? (
            <Card>
              <Text accessibilityRole="alert" style={{ fontSize: t.fontSizes.body, lineHeight: 26, color: t.colors.negative }}>
                {step.message}
              </Text>
            </Card>
          ) : null}
          <BodyText>Name for this phone (shown on your computer)</BodyText>
          <TextInput
            accessibilityLabel="Name for this phone"
            value={phoneName}
            onChangeText={setPhoneName}
            maxLength={50}
            style={inputStyle}
          />
          {canScan ? <BigButton label="Scan the code" onPress={startScan} /> : null}
          <BigButton label="Type the code instead" onPress={() => setStep({ name: 'typing' })} />
        </>
      ) : null}

      {step.name === 'scanning' ? (
        <>
          <View style={{ height: 360, borderRadius: t.radius.md, overflow: 'hidden' }}>
            <CameraView
              style={{ flex: 1 }}
              facing="back"
              barcodeScannerSettings={{ barcodeTypes: ['qr'] }}
              onBarcodeScanned={({ data }) => void pair(data)}
            />
          </View>
          <BodyText muted>Hold your phone so the whole code on your computer fits on the screen.</BodyText>
          <BigButton label="Cancel" onPress={() => setStep({ name: 'start' })} />
        </>
      ) : null}

      {step.name === 'typing' ? (
        <>
          <BodyText>
            On your computer, under the code, choose Show code as text. Then type or paste that text here.
          </BodyText>
          <TextInput
            accessibilityLabel="Pairing code text"
            value={typed}
            onChangeText={setTyped}
            multiline
            autoCapitalize="none"
            autoCorrect={false}
            style={[inputStyle, { minHeight: 140, textAlignVertical: 'top' }]}
          />
          <BigButton label="Connect" disabled={!typed.trim()} onPress={() => void pair(typed)} />
          <BigButton label="Back" onPress={() => setStep({ name: 'start' })} />
        </>
      ) : null}

      {step.name === 'confirm' ? (
        <>
          <Card>
            <BodyText>{DIFFERENT_COMPUTER_QUESTION}</BodyText>
          </Card>
          <BigButton label="Connect to this one" onPress={() => void pair(step.text, true)} />
          <BigButton label="Cancel" onPress={() => setStep({ name: 'start' })} />
        </>
      ) : null}

      {step.name === 'working' ? <BodyText>Connecting to your computer. This takes a few seconds...</BodyText> : null}

      {step.name === 'done' ? (
        <Card>
          <BodyText>{`Connected to ${step.computer}.`}</BodyText>
          <BodyText muted>
            Your phone and computer are paired. On your computer you should see "New phone paired".
          </BodyText>
        </Card>
      ) : null}
    </Screen>
  );
}
