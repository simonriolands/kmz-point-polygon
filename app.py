import streamlit as st
import zipfile
import os
import xml.etree.ElementTree as ET
import pandas as pd
from shapely.geometry import Point, Polygon

# === KONFIGURASI HALAMAN ===
st.set_page_config(page_title="KMZ Point to Polygon Processing", layout="centered")

st.title("🗺️ Pemrosesan Spatial Join Point ke Polygon (KMZ)")
st.write("Unggah file KMZ Anda untuk mendeteksi titik di dalam polygon secara otomatis.")

# === FUNGSI BANTU PARSER KML UNTUK MENJEJAK NAMA FOLDER ===
def parse_kml_hierarchy(kml_path):
    polygon_list = []
    point_list = []
    polygon_id_counter = 1

    tree = ET.parse(kml_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    # Fungsi rekursif untuk mendeteksi nama folder aktif di setiap level hierarki
    def walk_nodes(node, parent_folder="Tanpa_Folder"):
        nonlocal polygon_id_counter

        for child in node:
            tag = child.tag.split('}')[-1]
            
            # Tentukan nama folder saat ini jika elemen adalah Folder atau Document
            current_folder = parent_folder
            if tag in ['Folder', 'Document']:
                name_el = child.find('kml:name', ns)
                if name_el is not None and name_el.text:
                    current_folder = name_el.text.strip()

            if tag == 'Placemark':
                name_el = child.find('kml:name', ns)
                placemark_name = name_el.text.strip() if name_el is not None and name_el.text else "Tanpa_Nama"
                
                # Ekstrak FDT dari nama folder (misal: "FDT-01 - Area A" -> "FDT-01")[cite: 1]
                fdt_val = current_folder.split(" - ")[0].strip() if " - " in current_folder else current_folder

                # Cek apakah Polygon
                polygon_elem = child.find('.//kml:Polygon', ns)
                if polygon_elem is not None:
                    coords_elem = polygon_elem.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        coords = []
                        for tuple_str in coords_elem.text.strip().split():
                            parts = tuple_str.split(',')
                            if len(parts) >= 2:
                                coords.append((float(parts[0]), float(parts[1])))
                        if len(coords) >= 3:
                            poly = Polygon(coords)
                            polygon_list.append({
                                "geometry": poly,
                                "Polygon_Name": placemark_name,
                                "Polygon_ID": polygon_id_counter,
                                "FDT": fdt_val
                            })
                            polygon_id_counter += 1

                # Cek apakah Point
                point_elem = child.find('.//kml:Point', ns)
                if point_elem is not None:
                    coords_elem = point_elem.find('.//kml:coordinates', ns)
                    if coords_elem is not None and coords_elem.text:
                        parts = coords_elem.text.strip().split(',')
                        if len(parts) >= 2:
                            lon, lat = float(parts[0]), float(parts[1])
                            pt = Point(lon, lat)
                            point_list.append({
                                "geometry": pt,
                                "Latitude": lat,
                                "Longitude": lon,
                                "Point_Name": placemark_name
                            })

            # Lanjutkan penelusuran ke dalam node anak
            walk_nodes(child, current_folder)

    walk_nodes(root)
    return polygon_list, point_list

# === UPLOAD FILE ===
uploaded_file = st.file_uploader("Pilih file KMZ", type=["kmz"])

if uploaded_file is not None:
    temp_folder = "temp_kmz"
    os.makedirs(temp_folder, exist_ok=True)
    kml_file = "doc.kml"
    output_csv = "hasil_point_polygon.csv"
    kml_path = os.path.join(temp_folder, kml_file)

    with st.spinner("Mengekstrak dan memproses file KMZ..."):
        try:
            # === EKSTRAK KMZ ===
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                zip_ref.extractall(temp_folder)

            if not os.path.exists(kml_path):
                st.error("❌ File 'doc.kml' tidak ditemukan di dalam arsip KMZ.")
            else:
                polygon_list, point_list = parse_kml_hierarchy(kml_path)

                # === VALIDASI DATA ===
                if not polygon_list:
                    st.error("❌ Tidak ditemukan polygon di file KMZ.")
                elif not point_list:
                    st.error("❌ Tidak ditemukan point di file KMZ.")
                else:
                    # === Spatial Join Manual dengan Shapely ===
                    results = []
                    for pt_data in point_list:
                        pt_geom = pt_data["geometry"]
                        matched_poly_name = "-"
                        matched_poly_id = "-"
                        fdt_val = "-"

                        for poly_data in polygon_list:
                            if poly_data["geometry"].contains(pt_geom):
                                matched_poly_name = poly_data["Polygon_Name"]
                                matched_poly_id = poly_data["Polygon_ID"]
                                fdt_val = poly_data["FDT"]
                                break

                        results.append({
                            "Point_Name": pt_data["Point_Name"],
                            "Latitude": pt_data["Latitude"],
                            "Longitude": pt_data["Longitude"],
                            "Polygon_Name": matched_poly_name,
                            "Polygon_ID": matched_poly_id,
                            "FDT": fdt_val
                        })

                    final_result = pd.DataFrame(results)
                    final_result.to_csv(output_csv, index=False)

                    st.success("✅ Pemrosesan berhasil dilakukan!")
                    
                    # Tampilkan pratinjau
                    st.subheader("Pratinjau Hasil:")
                    st.dataframe(final_result.head(10))

                    # Tombol Unduh CSV
                    with open(output_csv, "rb") as f:
                        st.download_button(
                            label="📥 Unduh Hasil CSV",
                            data=f,
                            file_name="hasil_point_polygon.csv",
                            mime="text/csv"
                        )

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses file: {e}")
