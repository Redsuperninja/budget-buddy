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

// Deterministic-enough random bytes for tests (real app uses the phone's secure random).
jest.mock('expo-crypto', () => ({
  getRandomBytes: (n: number) => require('crypto').randomBytes(n),
}));
