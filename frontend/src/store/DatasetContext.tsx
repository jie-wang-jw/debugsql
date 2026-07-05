import {
  createContext,
  useContext,
  useCallback,
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

  const setDbType = useCallback((dbType: DbType) => {
    setSelection((prev) => {
      if (dbType === 'multimodal_demo') {
        return { dbType, benchmark: 'multimodal_demo', dbId: 'multimodal_demo' };
      }
      if (dbType === 'sqlite_benchmark' && prev.benchmark === 'multimodal_demo') {
        return { dbType, benchmark: 'spider', dbId: '' };
      }
      return { ...prev, dbType };
    });
  }, []);

  const setBenchmark = useCallback((benchmark: string) => {
    setSelection((prev) => {
      if (benchmark === 'multimodal_demo') {
        return { dbType: 'multimodal_demo', benchmark, dbId: 'multimodal_demo' };
      }
      if (prev.dbType === 'multimodal_demo') {
        return { dbType: 'sqlite_benchmark', benchmark, dbId: '' };
      }
      return { ...prev, benchmark };
    });
  }, []);

  const setDbId = useCallback((dbId: string) => {
    setSelection((prev) => ({ ...prev, dbId }));
  }, []);

  const value = useMemo<DatasetContextValue>(
    () => ({
      selection,
      setDbType,
      setBenchmark,
      setDbId,
    }),
    [selection, setBenchmark, setDbId, setDbType],
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
