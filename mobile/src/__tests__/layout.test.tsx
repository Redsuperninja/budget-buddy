import AsyncStorage from '@react-native-async-storage/async-storage';
import { renderRouter, screen } from 'expo-router/testing-library';

import RootLayout from '@/app/_layout';
import HomeScreen from '@/app/index';

// metro.config.js points expo-router's own imports of @expo/ui and expo-symbols at this stand-in (they
// bring a 966 KB font and react-native-worklets that this app never uses). Use the same stand-in here, so
// the tabs are tested without those modules.
jest.mock('expo-symbols', () => require('../../metro/unusedNativeUi'));
jest.mock('@expo/ui/jetpack-compose', () => require('../../metro/unusedNativeUi'), { virtual: true });
jest.mock('@expo/ui/jetpack-compose/modifiers', () => require('../../metro/unusedNativeUi'), { virtual: true });

beforeEach(async () => {
  await AsyncStorage.clear();
});

describe('metro stand-in for modules expo-router does not need here', () => {
  it('answers anything with a function that returns null, so expo-router can load', () => {
    const standIn = require('../../metro/unusedNativeUi');
    expect(standIn.__esModule).toBe(true);
    expect((0, standIn.fillMaxHeight)()).toBeNull();
    expect(standIn.Host({})).toBeNull();
  });
});

describe('root layout without @expo/ui and expo-symbols', () => {
  it('shows the Home screen with the four tabs', async () => {
    await renderRouter({ _layout: RootLayout, index: HomeScreen, 'add-receipt': () => null, taxes: () => null, settings: () => null, pair: () => null });

    expect(await screen.findByText('Your budget')).toBeTruthy();
    for (const title of ['Home', 'Add Receipt', 'Taxes', 'Settings']) {
      expect(screen.getAllByText(title).length).toBeGreaterThan(0);
    }
    // Pair is reached from Settings, not a tab.
    expect(screen.queryByText('Connect')).toBeNull();
  });
});
