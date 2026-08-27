import { MapContainer, TileLayer, CircleMarker, Popup } from "react-leaflet";
import { Link } from "react-router-dom";
import type { MapMarker } from "@/types";
import { PriorityBadge, StatusBadge, DemoBadge } from "@/components/Badges";

const PRIORITY_COLOR: Record<string, string> = {
  LOW: "#94a3b8",
  MEDIUM: "#f59e0b",
  HIGH: "#f97316",
  CRITICAL: "#dc2626",
};

export function IssueMap({ markers, center }: { markers: MapMarker[]; center: [number, number] }) {
  return (
    <MapContainer center={center} zoom={12} className="h-full w-full rounded-2xl">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {markers.map((m) => (
        <CircleMarker
          key={m.id}
          center={[m.latitude, m.longitude]}
          radius={m.priority_level === "CRITICAL" ? 10 : 7}
          pathOptions={{
            color: PRIORITY_COLOR[m.priority_level] || "#64748b",
            fillColor: PRIORITY_COLOR[m.priority_level] || "#64748b",
            fillOpacity: 0.8,
          }}
        >
          <Popup>
            <div className="min-w-[180px]">
              <div className="flex items-center gap-2">
                <p className="font-bold text-slate-800">{m.complaint_id}</p>
                {m.is_demo && <DemoBadge />}
              </div>
              <p className="text-sm text-slate-700">{m.issue_type}</p>
              <div className="my-1 flex gap-1">
                <PriorityBadge level={m.priority_level} />
                <StatusBadge status={m.status} />
              </div>
              <p className="text-xs text-slate-500">{m.reporter_count} reporter(s) · {m.department || "Unassigned"}</p>
              <Link to={`/staff/issues/${m.id}`} className="mt-1 inline-block text-xs font-semibold text-brand-700 underline">
                View details →
              </Link>
            </div>
          </Popup>
        </CircleMarker>
      ))}
    </MapContainer>
  );
}
