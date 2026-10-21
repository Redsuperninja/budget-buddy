// Metro (the app bundler) settings. One change: keep parts of expo-router that this app never uses out of
// the bundle. expo-router's Stack toolbar and native tabs (Android versions) pull in @expo/ui and
// expo-symbols, which add the 966 KB Material Symbols font and react-native-worklets. This app only uses
// the JS `Tabs` navigator and never `Stack.Toolbar` or native tabs, so only expo-router's own imports are
// pointed at a stand-in (metro/unusedNativeUi.js). Nothing else is touched.
const path = require('path');
const { getDefaultConfig } = require('expo/metro-config');

const config = getDefaultConfig(__dirname);
const standIn = path.join(__dirname, 'metro', 'unusedNativeUi.js');
const leftOut = /^(@expo\/ui(\/.*)?|expo-symbols)$/;
const fromRouter = /[\\/]node_modules[\\/]expo-router[\\/]/;

const defaultResolve = config.resolver.resolveRequest;
config.resolver.resolveRequest = (context, moduleName, platform) => {
  if (leftOut.test(moduleName) && fromRouter.test(context.originModulePath)) {
    return { type: 'sourceFile', filePath: standIn };
  }
  return (defaultResolve ?? context.resolveRequest)(context, moduleName, platform);
};

module.exports = config;
