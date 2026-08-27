import { useState } from "react";
import { MapContainer, TileLayer, Marker, useMapEvents } from "react-leaflet";
import { useTranslation } from "@/hooks/useTranslation";

const DEFAULT_CENTER: [number, number] = [13.0827, 80.2707];

function ClickCapture({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({
    click(e) {
      onPick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

/**
 * Tappable map for manual location selection when GPS fails — the
 * citizen actively picks a point (nothing is ever auto-selected or
 * defaulted to a hardcoded city coordinate). Shared by the report
 * wizard's LocationStep and NearbyIssuesPage.
 */
export function LocationPickerMap({
  initialCenter,
  onConfirm,
}: {
  initialCenter?: [number, number];
  onConfirm: (lat: number, lng: number) => void;
}) {
  const { t } = useTranslation();
  const [picked, setPicked] = useState<[number, number] | null>(null);

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-3">
      <p className="text-sm text-slate-600">{t.tapMapToChoose}</p>
      <div className="h-64 w-full overflow-hidden rounded-lg">
        <MapContainer center={initialCenter || DEFAULT_CENTER} zoom={13} className="h-full w-full">
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
            url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
          />
          <ClickCapture onPick={(lat, lng) => setPicked([lat, lng])} />
          {picked && <Marker position={picked} />}
        </MapContainer>
      </div>
      {picked && (
        <p className="text-xs text-slate-500">
          {picked[0].toFixed(5)}, {picked[1].toFixed(5)}
        </p>
      )}
      <button className="btn-primary" disabled={!picked} onClick={() => picked && onConfirm(picked[0], picked[1])}>
        {t.useThisLocation}
      </button>
    </div>
  );
}
