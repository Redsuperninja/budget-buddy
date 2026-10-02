import Ionicons from '@expo/vector-icons/Ionicons';
import { Tabs } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import type { ComponentProps } from 'react';
import type { ColorValue } from 'react-native';

import { useTheme } from '@/theme';

type IconName = ComponentProps<typeof Ionicons>['name'];

function tabIcon(name: IconName) {
  return ({ color, size }: { color: ColorValue; size: number }) => (
    <Ionicons name={name} color={color} size={size + 4} />
  );
}

export default function RootLayout() {
  const t = useTheme();
  return (
    <>
      <StatusBar style={t.dark ? 'light' : 'dark'} />
      <Tabs
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: t.colors.primary,
          tabBarInactiveTintColor: t.colors.tabInactive,
          tabBarLabelStyle: { fontSize: t.fontSizes.small - 2, fontWeight: '600' },
          tabBarStyle: {
            backgroundColor: t.colors.background,
            borderTopColor: t.colors.border,
            minHeight: t.minTouchSize + 16,
            paddingTop: t.spacing.xs,
          },
          sceneStyle: { backgroundColor: t.colors.background },
        }}>
        <Tabs.Screen name="index" options={{ title: 'Home', tabBarIcon: tabIcon('home') }} />
        <Tabs.Screen
          name="add-receipt"
          options={{ title: 'Add Receipt', tabBarIcon: tabIcon('camera') }}
        />
        <Tabs.Screen name="taxes" options={{ title: 'Taxes', tabBarIcon: tabIcon('document-text') }} />
        <Tabs.Screen
          name="settings"
          options={{ title: 'Settings', tabBarIcon: tabIcon('settings') }}
        />
      </Tabs>
    </>
  );
}
