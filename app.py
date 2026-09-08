import streamlit as st
import zipfile
import os
import geopandas as gpd
import pandas as pd
import fiona

# === KONFIGURASI HALAMAN ===
st.set_page_config(page_title="KMZ Point to Polygon Processing", layout="centered")

st.title("🗺️ Pemrosesan Spatial Join Point ke Polygon (KMZ)")
st.write("Unggah file KMZ Anda untuk mendeteksi titik di dalam polygon secara otomatis.")

# === UPLOAD FILE ===
uploaded_file = st.file_uploader("Pilih file KMZ", type=["kmz"])

if uploaded_file is not None:
    temp_folder = "temp_kmz"
    os.makedirs(temp_folder, exist_ok=True)
    kml_file = "doc.kml"
    output_csv = "hasil_point_polygon.csv"
    kml_path = os.path.join(temp_folder, kml_file)

    with st.spinner("Mengekstrak dan memproses file KMZ..."):
        # === EKSTRAK KMZ ===
        with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
            zip_ref.extractall(temp_folder)

        # === BACA SEMUA LAYER ===
        try:
            layers = fiona.listlayers(kml_path)
            st.info(f"Layer ditemukan: {len(layers)} layer")

            polygon_list = []
            point_list = []
            polygon_id_counter = 1  # Untuk membuat ID unik tiap polygon

            for layer in layers:
                try:
                    gdf = gpd.read_file(kml_path, driver="KML", layer=layer)
                    if gdf.empty:
                        continue

                    geom_types = gdf.geometry.type.unique()
                    
                    # Ekstrak nama folder (FDT) dari nama layer, misalnya "FDT-01 - Area A" -> "FDT-01"[cite: 1]
                    fdt_name = layer.split(" - ")[0].strip()

                    if any(t in ['Polygon', 'MultiPolygon'] for t in geom_types):
                        for _, row in gdf.iterrows():
                            polygon_list.append({
                                "geometry": row.geometry,
                                "Polygon_Name": row.get("Name", "Tanpa_Nama"),
                                "Polygon_ID": polygon_id_counter,
                                "FDT": fdt_name
                            })
                            polygon_id_counter += 1

                    elif 'Point' in geom_types:
                        for _, row in gdf.iterrows():
                            point_list.append({
                                "geometry": row.geometry,
                                "Latitude": row.geometry.y,
                                "Longitude": row.geometry.x,
                                "Point_Name": row.get("Name", "Tanpa_Nama")
                            })

                except Exception as e:
                    st.warning(f"Gagal baca layer '{layer}': {e}")
                    continue

            # === VALIDASI DATA ===
            if not polygon_list:
                st.error("❌ Tidak ditemukan polygon di file KMZ.")
            elif not point_list:
                st.error("❌ Tidak ditemukan point di file KMZ.")
            else:
                # === Gabungkan dan buat GeoDataFrame ===[cite: 1]
                polygon_gdf = gpd.GeoDataFrame(polygon_list, geometry="geometry")
                point_gdf = gpd.GeoDataFrame(point_list, geometry="geometry", crs=polygon_gdf.crs)

                # === Spatial Join: apakah point berada dalam polygon ===[cite: 1]
                joined = gpd.sjoin(point_gdf, polygon_gdf, how="left", predicate="within")

                # === Format Hasil Akhir ===[cite: 1]
                final_result = joined[["Point_Name", "Latitude", "Longitude", "Polygon_Name", "Polygon_ID", "FDT"]]
                
                # Simpan ke file sementara
                final_result.to_csv(output_csv, index=False)

                st.success("✅ Pemrosesan berhasil dilakukan!")
                
                # Tampilkan pratinjau data di web
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
            st.error(f"Terjadi kesalahan saat memproses file KML/KMZ: {e}")