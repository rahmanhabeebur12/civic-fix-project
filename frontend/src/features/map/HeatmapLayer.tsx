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
 *
 * `maxZoom` MUST match the map's actual initial zoom (see the
 * <MapContainer zoom={...}> this layer is mounted inside). leaflet.heat
 * dims every point by 1/2^(maxZoom - currentZoom) — with maxZoom set
 * higher than the zoom the map is actually viewed at, every point was
 * being rendered at a small fraction of its real opacity (near-invisible
 * but technically present, which is why this looked "broken" rather than
 * erroring). At maxZoom === current zoom, points render at full
 * intensity by default and only dim if the staff zooms out further.
 */
const HEATMAP_MAX_ZOOM = 12;

export function HeatmapLayer({ points }: { points: HeatmapPoint[] }) {
  const map = useMap();

  useEffect(() => {
    if (!points.length) return;
    const layer = (L as any)
      .heatLayer(
        points.map((p) => [p.latitude, p.longitude, p.weight]),
        { radius: 28, blur: 20, maxZoom: HEATMAP_MAX_ZOOM }
      )
      .addTo(map);

    // The map itself stays mounted across filter changes (see
    // AnalyticsPage.tsx) rather than being torn down and rebuilt, so this
    // layer is responsible for panning to the new data whenever the
    // filtered point set changes — otherwise a result far from the map's
    // fixed initial center could render fully off-screen.
    if (points.length === 1) {
      map.setView([points[0].latitude, points[0].longitude], HEATMAP_MAX_ZOOM);
    } else {
      map.fitBounds(
        L.latLngBounds(points.map((p) => [p.latitude, p.longitude] as [number, number])),
        { maxZoom: HEATMAP_MAX_ZOOM + 2, padding: [24, 24] }
      );
    }

    return () => {
      map.removeLayer(layer);
    };
  }, [map, points]);

  return null;
}
