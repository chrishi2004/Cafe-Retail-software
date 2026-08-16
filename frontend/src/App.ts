// P3 entry shim: Vite/TypeScript resolve .ts before .tsx for extensionless
// imports, so the existing main.tsx now boots the portal router while the
// original Retail app remains available explicitly as App.tsx.
export { default } from "./PortalRoot";
