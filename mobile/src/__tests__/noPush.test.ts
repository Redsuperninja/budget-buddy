/**
 * Reminders are local notifications only. expo-notifications also ships push plumbing (Firebase on
 * Android, the push entitlement on iOS), which stays off as long as nothing asks for a push token and
 * there's no Firebase config. This fails if either ever appears, so turning push on is a decision.
 */
declare const require: (name: string) => any;
declare const __dirname: string;

const { readdirSync, readFileSync, existsSync, statSync } = require('fs');
const { join } = require('path');

const MOBILE = join(__dirname, '..', '..');

function sourceFiles(dir: string): string[] {
  return readdirSync(dir).flatMap((name: string) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === '__tests__' ? [] : sourceFiles(path);
    return /\.(ts|tsx)$/.test(name) ? [path] : [];
  });
}

test('the app never asks for a push token', () => {
  const found = sourceFiles(join(MOBILE, 'src')).filter((f) =>
    /getExpoPushTokenAsync|getDevicePushTokenAsync|addPushTokenListener/.test(readFileSync(f, 'utf8')),
  );
  expect(found).toEqual([]);
});

test('there is no Firebase or push config', () => {
  expect(existsSync(join(MOBILE, 'google-services.json'))).toBe(false);
  expect(existsSync(join(MOBILE, 'GoogleService-Info.plist'))).toBe(false);
  expect(readFileSync(join(MOBILE, 'app.json'), 'utf8')).not.toMatch(/googleServicesFile|"mode":\s*"production"/);
});
