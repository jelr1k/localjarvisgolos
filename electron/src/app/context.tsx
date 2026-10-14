import { createContext, useContext, useEffect, useReducer, type PropsWithChildren } from "react";
import { appReducer, loadInitialState, STORAGE_KEY } from "./state";
import type { AppState, AppAction } from "./types";

interface AppContextValue {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const AppContext = createContext<AppContextValue | null>(null);

export function AppProvider({ children }: PropsWithChildren) {
  const [state, dispatch] = useReducer(appReducer, undefined, loadInitialState);

  useEffect(() => {
    try {
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify({
        interfaceMode: state.interfaceMode,
        settings: state.settings
      }));
      window.localStorage.setItem("jarvis-interface", state.interfaceMode);
      window.localStorage.setItem("jarvis-theme", state.settings.appearance.theme);
    } catch (error) {
      console.warn("Не удалось сохранить настройки интерфейса.", error);
    }
  }, [state.interfaceMode, state.settings]);

  return <AppContext.Provider value={{ state, dispatch }}>{children}</AppContext.Provider>;
}

export function useAppState(): AppContextValue {
  const context = useContext(AppContext);
  if (!context) throw new Error("useAppState должен вызываться внутри AppProvider.");
  return context;
}
