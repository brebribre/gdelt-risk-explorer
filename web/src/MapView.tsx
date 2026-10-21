import { useEffect } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import { latLngBounds } from "leaflet";
import { Point, fmtNum } from "./lib";

type Props = { points: Point[]; selected: string; onSelect: (place: string) => void };

/** Zoom to the results when they are few enough to be a focused set; otherwise show the world. */
function FitToPoints({ points }: { points: Point[] }) {
  const map = useMap();
  const key = points.map((p) => p.name).join("|");
  useEffect(() => {
    const coords = points
      .filter((p) => Number.isFinite(p.lat) && Number.isFinite(p.lon))
      .map((p) => [p.lat, p.lon] as [number, number]);
    const bounds = coords.length ? latLngBounds(coords) : null;
    if (bounds?.isValid() && coords.length <= 150) {
      map.invalidateSize();
      map.fitBounds(bounds, { padding: [40, 40], maxZoom: 7 });
    } else {
      map.setView([20, 30], 2);
    }
  }, [key, map]); // eslint-disable-line react-hooks/exhaustive-deps -- `key` stands in for `points`
  return null;
}

export default function MapView({ points, selected, onSelect }: Props) {
  const max = Math.max(1, ...points.map((p) => p.n));
  return (
    <MapContainer center={[20, 30]} zoom={2} minZoom={2} worldCopyJump preferCanvas className="map">
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <FitToPoints points={points} />
      {/* Draw small circles last so they stay clickable on top of big ones */}
      {[...points].sort((a, b) => b.n - a.n).map((p) => {
        const isSel = p.name === selected;
        return (
          <CircleMarker
            key={p.name}
            center={[p.lat, p.lon]}
            radius={3 + Math.sqrt(p.n / max) * 22}
            pathOptions={{
              color: isSel ? "#111" : p.precise ? "#c0392b" : "#7f8c9a",
              weight: isSel ? 3 : 1,
              fillColor: p.precise ? "#e74c3c" : "#95a5b5",
              fillOpacity: 0.45,
            }}
            eventHandlers={{ click: () => onSelect(isSel ? "" : p.name) }}
          >
            <Tooltip>
              <strong>{p.name}</strong>
              <br />
              {fmtNum(p.n)} articles{p.precise ? "" : " · country/region centroid"}
            </Tooltip>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
