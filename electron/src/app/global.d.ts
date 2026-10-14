export {};

declare global {
  interface Window {
    jarvis?: {
      version: string;
      mode: "ui-prototype";
      restartApp: () => Promise<void>;
    };
  }
}
