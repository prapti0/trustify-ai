import type { EngineCapability } from "../api/types";

export interface EngineCounts {
  ready: number;
  notIntegrated: number;
}

export function countEngines(engines: Pick<EngineCapability, "status">[]): EngineCounts {
  return {
    ready: engines.filter((engine) => engine.status === "ready").length,
    notIntegrated: engines.filter((engine) => engine.status === "not_integrated").length,
  };
}
