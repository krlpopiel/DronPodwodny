import csv
import folium

def nmea_to_decimal(coord, direction):
    """Konwertuje współrzędne NMEA (DDMM.MMMM) na format dziesiętny."""
    if not coord or coord == "":
        return None
    deg = int(coord[:2 if direction in ['N','S'] else 3])
    minutes = float(coord[2 if direction in ['N','S'] else 3:])
    decimal = deg + minutes / 60
    if direction in ['S','W']:
        decimal *= -1
    return decimal

def main():
    print("=== Rysowanie trasy GPS z pliku CSV ===")
    filename = input("Podaj nazwę pliku CSV (np. dane_gps.csv): ").strip()

    points = []  # lista (lat, lon, timestamp)

    try:
        with open(filename, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                data = row['dane']
                timestamp = row['timestamp']
                if data.startswith("$GPRMC"):
                    parts = data.split(',')
                    if len(parts) > 6 and parts[2] == 'A':
                        lat = nmea_to_decimal(parts[3], parts[4])
                        lon = nmea_to_decimal(parts[5], parts[6])
                        if lat and lon:
                            points.append((lat, lon, timestamp))
    except FileNotFoundError:
        print(f"❌ Nie znaleziono pliku: {filename}")
        return
    except KeyError:
        print("❌ Plik musi zawierać kolumny: 'timestamp' oraz 'dane'.")
        return

    if not points:
        print("⚠️ Nie znaleziono żadnych współrzędnych GPS w pliku.")
        return

    # Utworzenie mapy
    start_point = (points[0][0], points[0][1])
    m = folium.Map(location=start_point, zoom_start=17)

    # Linia trasy
    folium.PolyLine([(p[0], p[1]) for p in points], color="blue", weight=3, opacity=0.8).add_to(m)

    # Dodanie znaczników z timestampami
    for i, (lat, lon, ts) in enumerate(points):
        popup_text = f"<b>Punkt {i+1}</b><br>{ts}"
        folium.CircleMarker(
            location=(lat, lon),
            radius=4,
            color="red",
            fill=True,
            fill_color="red",
            fill_opacity=0.8,
            popup=folium.Popup(popup_text, max_width=250)
        ).add_to(m)

    # Znaczniki startu i końca
    folium.Marker((points[0][0], points[0][1]), tooltip="Start", icon=folium.Icon(color='green')).add_to(m)
    folium.Marker((points[-1][0], points[-1][1]), tooltip="Koniec", icon=folium.Icon(color='red')).add_to(m)

    output_file = "trasa.html"
    m.save(output_file)
    print(f"✅ Zapisano mapę do pliku: {output_file}")
    print("🌍 Otwórz plik w przeglądarce, aby zobaczyć trasę i timestampy.")

if __name__ == "__main__":
    main()
