// In-memory AsyncStorage for tests (the real one needs a phone).
jest.mock('@react-native-async-storage/async-storage', () =>
  require('@react-native-async-storage/async-storage/jest/async-storage-mock'),
);

// In-memory secure store for tests.
jest.mock('expo-secure-store', () => {
  const store = new Map<string, string>();
  return {
    setItemAsync: async (k: string, v: string) => void store.set(k, v),
    getItemAsync: async (k: string) => store.get(k) ?? null,
    deleteItemAsync: async (k: string) => void store.delete(k),
  };
});

// Local notifications for tests: remembers what's scheduled, permission granted unless a test says no.
jest.mock('expo-notifications', () => {
  const scheduled = new Map<string, unknown>();
  return {
    __scheduled: scheduled,
    __permission: { granted: true },
    AndroidImportance: { DEFAULT: 3 },
    SchedulableTriggerInputTypes: { DATE: 'date' },
    getPermissionsAsync: jest.fn(async () => require('expo-notifications').__permission),
    requestPermissionsAsync: jest.fn(async () => require('expo-notifications').__permission),
    setNotificationChannelAsync: jest.fn(async () => null),
    scheduleNotificationAsync: jest.fn(async (r: { identifier: string }) => {
      scheduled.set(r.identifier, r);
      return r.identifier;
    }),
    cancelScheduledNotificationAsync: jest.fn(async (id: string) => void scheduled.delete(id)),
  };
});

// Deterministic-enough random bytes for tests (real app uses the phone's secure random).
jest.mock('expo-crypto', () => ({
  getRandomBytes: (n: number) => require('crypto').randomBytes(n),
}));
