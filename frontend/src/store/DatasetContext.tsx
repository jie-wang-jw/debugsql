import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import type { DbType } from '../services/api/capabilitiesApi';

export interface DatasetSelection {
  dbType: DbType;
  benchmark: string;
  dbId: string;
}

interface DatasetContextValue {
  selection: DatasetSelection;
  setDbType: (dbType: DbType) => void;
  setBenchmark: (benchmark: string) => void;
  setDbId: (dbId: string) => void;
}

const DatasetContext = createContext<DatasetContextValue | null>(null);

const DEFAULT_SELECTION: DatasetSelection = {
  dbType: 'sqlite_benchmark',
  benchmark: 'spider',
  dbId: '',
};

export function DatasetProvider({ children }: { children: ReactNode }) {
  const [selection, setSelection] = useState<DatasetSelection>(DEFAULT_SELECTION);

  const value = useMemo<DatasetContextValue>(
    () => ({
      selection,
      setDbType: (dbType) => setSelection((prev) => ({ ...prev, dbType })),
      setBenchmark: (benchmark) => setSelection((prev) => ({ ...prev, benchmark })),
      setDbId: (dbId) => setSelection((prev) => ({ ...prev, dbId })),
    }),
    [selection],
  );

  return <DatasetContext.Provider value={value}>{children}</DatasetContext.Provider>;
}

export function useDatasetContext(): DatasetContextValue {
  const ctx = useContext(DatasetContext);
  if (!ctx) {
    throw new Error('useDatasetContext must be used inside <DatasetProvider>');
  }
  return ctx;
}
