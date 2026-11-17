import { useEffect, useState } from "react";
import { getPlatform } from "../api/client";
import type { PlatformStatus } from "../api/types";
import { CapabilityChart } from "../components/CapabilityChart";
import { countEngines } from "../lib/capabilities";

export function StatusPage() {
  const [platform, setPlatform] = useState<PlatformStatus | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getPlatform()
      .then((status) => {
        if (active) {
          setPlatform(status);
        }
      })
      .catch(() => {
        if (active) {
          setError("The platform API is unreachable. Start the API, then refresh. No capability data is substituted.");
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <p role="alert" className="max-w-2xl text-sm text-amber-200">
        {error}
      </p>
    );
  }

  if (!platform) {
    return <p className="text-sm text-zinc-400">Loading platform status…</p>;
  }

  const counts = countEngines(platform.engines);

  return (
    <div className="mx-auto max-w-5xl">
      <p className="font-mono text-xs tracking-[0.16em] text-zinc-500">
        {platform.name} {platform.version}
      </p>
      <h1 className="mt-3 text-3xl font-medium text-zinc-50">System status</h1>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-zinc-400">
        Engine counts come from <span className="font-mono text-zinc-300">GET /api/v1/platform</span>.
        A runtime tool can be installed while its detector stays not integrated.
        Authentication is {platform.auth_configured ? "configured" : "not configured"}. Storage
        backend is {platform.storage_backend}. Current upload limit:{" "}
        {platform.max_upload_bytes.toLocaleString()} bytes.
      </p>

      <section className="mt-8">
        <h2 className="text-lg font-medium text-zinc-100">Engines by integration state</h2>
        <p className="mt-1 text-sm text-zinc-500">
          {counts.ready} ready, {counts.notIntegrated} not integrated. This is not detection accuracy.
        </p>
        <div className="mt-4 border border-zinc-800 bg-zinc-900 p-4">
          <CapabilityChart ready={counts.ready} notIntegrated={counts.notIntegrated} />
        </div>
      </section>

      <section className="mt-10">
        <h2 className="text-lg font-medium text-zinc-100">Guarantees</h2>
        <ul className="mt-3 space-y-2 text-sm text-zinc-300">
          {platform.guarantees.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </section>

      <section className="mt-10 overflow-x-auto">
        <h2 className="text-lg font-medium text-zinc-100">Engines</h2>
        <table className="mt-3 w-full min-w-[640px] border-collapse text-left text-sm">
          <thead className="text-zinc-500">
            <tr>
              <th className="border-b border-zinc-800 py-2 pr-4 font-medium">Engine</th>
              <th className="border-b border-zinc-800 py-2 pr-4 font-medium">Status</th>
              <th className="border-b border-zinc-800 py-2 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {platform.engines.map((engine) => (
              <tr key={engine.id}>
                <th scope="row" className="border-b border-zinc-900 py-3 pr-4 font-medium text-zinc-100">
                  {engine.name}
                  {engine.runtime.length > 0 && (
                    <span className="mt-1 block font-mono text-xs font-normal text-zinc-500">
                      {engine.runtime.map((probe) => `${probe.name}:${probe.present ? "present" : "missing"}`).join("  ")}
                    </span>
                  )}
                </th>
                <td className="border-b border-zinc-900 py-3 pr-4 text-zinc-300">{engine.status}</td>
                <td className="border-b border-zinc-900 py-3 text-zinc-400">{engine.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="mt-10 overflow-x-auto">
        <h2 className="text-lg font-medium text-zinc-100">Services</h2>
        <table className="mt-3 w-full min-w-[640px] border-collapse text-left text-sm">
          <thead className="text-zinc-500">
            <tr>
              <th className="border-b border-zinc-800 py-2 pr-4 font-medium">Service</th>
              <th className="border-b border-zinc-800 py-2 pr-4 font-medium">Phase</th>
              <th className="border-b border-zinc-800 py-2 pr-4 font-medium">State</th>
              <th className="border-b border-zinc-800 py-2 font-medium">Detail</th>
            </tr>
          </thead>
          <tbody>
            {platform.services.map((service) => (
              <tr key={service.id}>
                <th scope="row" className="border-b border-zinc-900 py-3 pr-4 font-medium text-zinc-100">
                  {service.name}
                </th>
                <td className="border-b border-zinc-900 py-3 pr-4 text-zinc-300">{service.phase}</td>
                <td className="border-b border-zinc-900 py-3 pr-4 font-mono text-xs text-zinc-300">{service.state}</td>
                <td className="border-b border-zinc-900 py-3 text-zinc-400">{service.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
