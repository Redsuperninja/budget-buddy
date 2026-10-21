// Stand-in for @expo/ui and expo-symbols inside expo-router (see metro.config.js). Anything asked for is
// a harmless function that returns null, so the few lines expo-router runs when it loads don't fail.
const nothing = () => null;
module.exports = new Proxy({}, { get: (_target, name) => (name === '__esModule' ? true : nothing) });
