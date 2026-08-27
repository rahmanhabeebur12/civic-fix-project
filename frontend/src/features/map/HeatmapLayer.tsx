import { useEffect } from "react";
import { useMap } from "react-leaflet";
import L from "leaflet";
import "leaflet.heat";
import type { HeatmapPoint } from "@/types";

/**
 * Imperative Leaflet layer (react-leaflet has no built-in heat component)
 * — intensity is driven by each point's occurrence-count `weight`, never
 * invented. Built from historical RESOLVED issues only (see
 * app/services/heatmap_service.py), never the live/unresolved map data.
 */
export function HeatmapLayer({ points }: { points: HeatmapPoint[] }) {
  const map = useMap();

  useEffect(() => {
    if (!points.length) return;
    const layer = (L as any)
      .heatLayer(
        points.map((p) => [p.latitude, p.longitude, p.weight]),
        { radius: 28, blur: 20, maxZoom: 16 }
      )
      .addTo(map);
    return () => {
      map.removeLayer(layer);
    };
  }, [map, points]);

  return null;
}
