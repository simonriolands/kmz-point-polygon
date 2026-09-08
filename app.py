import streamlit as st
import zipfile
import os
import geopandas as gpd
import pandas as pd

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
        try:
            # === EKSTRAK KMZ ===
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                zip_ref.extractall(temp_folder)

            if not os.path.exists(kml_path):
                st.error("❌ File 'doc.kml' tidak ditemukan di dalam arsip KMZ.")
            else:
                polygon_list = []
                point_list = []
                polygon_id_counter = 1

                # Menggunakan GeoPandas langsung untuk membaca KML tanpa fiona terpisah
                # GeoPandas menggunakan engine OGR yang membaca semua layer secara otomatis
                try:
                    # Mencoba membaca layer default atau iterasi layer menggunakan fiona tidak diperlukan lagi
                    # Kita bisa membaca langsung file kml menggunakan geopandas
                    # Karena KML bisa memiliki banyak layer, kita baca secara umum menggunakan driver KML
                    import fiona.drvsupport
                    fiona.drvsupport.supported_drivers['KML'] = 'rw'
                except:
                    pass

                # Membaca layer yang ada di dalam KML menggunakan fiona internal geopandas
                from shapely.geometry import shape
                import xml.etree.ElementTree as ET

                # Pendekatan alternatif langsung dengan GeoPandas membaca file kml
                # Geopandas read_file dapat membaca file KML langsung
                # Untuk mendeteksi layer, kita bisa membaca layer 0 atau membaca dengan fiona jika terbawa oleh geopandas dependensi internal
                
                # Cara paling aman menggunakan GeoPandas membaca kml langsung:
                # Mengingat OGR mendukung KML, kita baca langsung path-nya:
                # Cek layer apa saja yang tersedia melalui geopandas/fiona internal
                import fiona
                layers = fiona.listlayers(kml_path)
                st.info(f"Layer/Kategori ditemukan: {len(layers)} layer")

                for layer in layers:
                    try:
                        gdf = gpd.read_file(kml_path, driver="KML", layer=layer)
                        if gdf.empty:
                            continue

                        geom_types = gdf.geometry.type.unique()
                        fdt_name = layer.split(" - ")[0].strip() if " - " in layer else layer

                        if any(t in ['Polygon', 'MultiPolygon'] for t in geom_types):
                            for _, row in gdf.iterrows():
                                polygon_list.append({
                                    "geometry": row.geometry,
                                    "Polygon_Name": row.get("Name", "Tanpa_Nama"),
                                    "Polygon_ID": polygon_id_counter,
                                    "FDT": fdt_name
                                })
                                polygon_id_counter += 1

                        elif any(t in ['Point', 'MultiPoint'] for t in geom_types):
                            for _, row in gdf.iterrows():
                                point_list.append({
                                    "geometry": row.geometry,
                                    "Latitude": row.geometry.y,
                                    "Longitude": row.geometry.x,
                                    "Point_Name": row.get("Name", "Tanpa_Nama")
                                })
                    except Exception:
                        continue

                # === VALIDASI DATA ===
                if not polygon_list:
                    st.error("❌ Tidak ditemukan polygon di file KMZ.")
                elif not point_list:
                    st.error("❌ Tidak ditemukan point di file KMZ.")
                else:
                    # === Gabungkan dan buat GeoDataFrame ===
                    polygon_gdf = gpd.GeoDataFrame(polygon_list, geometry="geometry")
                    point_gdf = gpd.GeoDataFrame(point_list, geometry="geometry", crs=polygon_gdf.crs)

                    # === Spatial Join ===
                    joined = gpd.sjoin(point_gdf, polygon_gdf, how="left", predicate="within")

                    # === Format Hasil Akhir ===
                    final_result = joined[["Point_Name", "Latitude", "Longitude", "Polygon_Name", "Polygon_ID", "FDT"]]
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
