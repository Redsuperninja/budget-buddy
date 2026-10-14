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

// In-memory files for tests (receipt photos): paths joined like the real File/Directory classes.
jest.mock('expo-file-system', () => {
  const files = new Map<string, Uint8Array>();
  const join = (parts: unknown[]) => parts.map((p) => (typeof p === 'string' ? p : (p as { uri: string }).uri)).join('/');
  class Directory {
    uri: string;
    constructor(...parts: unknown[]) {
      this.uri = join(parts);
    }
    create() {}
    list() {
      return [...files.keys()]
        .filter((uri) => uri.startsWith(`${this.uri}/`) && !uri.slice(this.uri.length + 1).includes('/'))
        .map((uri) => new File(uri));
    }
  }
  class File {
    uri: string;
    constructor(...parts: unknown[]) {
      this.uri = join(parts);
    }
    get exists() {
      return files.has(this.uri);
    }
    get name() {
      return this.uri.split('/').pop() as string;
    }
    write(content: Uint8Array) {
      files.set(this.uri, new Uint8Array(content));
    }
    async bytes() {
      const data = files.get(this.uri);
      if (!data) throw new Error('missing file');
      return new Uint8Array(data);
    }
    delete() {
      files.delete(this.uri);
    }
  }
  return { __files: files, Directory, File, Paths: { document: new Directory('doc') } };
});

// Deterministic-enough random bytes for tests (real app uses the phone's secure random).
jest.mock('expo-crypto', () => ({
  getRandomBytes: (n: number) => require('crypto').randomBytes(n),
}));
