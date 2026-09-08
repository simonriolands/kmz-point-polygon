import streamlit as st
import zipfile
import os
import xml.etree.ElementTree as ET
import pandas as pd
from shapely.geometry import Point, Polygon

# === KONFIGURASI HALAMAN ===
st.set_page_config(page_title="KMZ Point to Polygon Processing", layout="wide")

st.title("🗺️ Pemrosesan Spatial Join & Rekapitulasi Point ke Polygon (KMZ)")
st.write("Unggah file KMZ Anda untuk mendeteksi titik di dalam polygon dan menyusun rekapitulasi secara otomatis.")

# === FUNGSI PARSER KML ===
def parse_kml_hierarchy(kml_path):
    polygon_list = []
    point_list = []

    tree = ET.parse(kml_path)
    root = tree.getroot()
    ns = {'kml': 'http://www.opengis.net/kml/2.2'}

    def walk_nodes(node, parent_folder="Tanpa_Folder"):
        for child in node:
            tag = child.tag.split('}')[-1]
            current_folder = parent_folder
            
            # Deteksi nama folder/grup
            if tag in ['Folder', 'Document']:
                name_el = child.find('kml:name', ns)
                if name_el is not None and name_el.text:
                    current_folder = name_el.text.strip()

            if tag == 'Placemark':
                name_el = child.find('kml:name', ns)
                placemark_name = name_el.text.strip() if name_el is not None and name_el.text else "Tanpa_Nama"
                
                # Ekstrak nama FDT dari nama folder
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
                                "FDT": fdt_val
                            })

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

            walk_nodes(child, current_folder)

    walk_nodes(root)
    return polygon_list, point_list

# === UPLOAD FILE ===
uploaded_file = st.file_uploader("Pilih file KMZ", type=["kmz"])

if uploaded_file is not None:
    temp_folder = "temp_kmz"
    os.makedirs(temp_folder, exist_ok=True)
    kml_file = "doc.kml"
    output_csv = "hasil_gabungan_detail_dan_rekap.csv"
    kml_path = os.path.join(temp_folder, kml_file)

    with st.spinner("Mengekstrak dan memproses file KMZ..."):
        try:
            with zipfile.ZipFile(uploaded_file, 'r') as zip_ref:
                zip_ref.extractall(temp_folder)

            if not os.path.exists(kml_path):
                st.error("❌ File 'doc.kml' tidak ditemukan di dalam arsip KMZ.")
            else:
                polygon_list, point_list = parse_kml_hierarchy(kml_path)

                if not polygon_list:
                    st.error("❌ Tidak ditemukan polygon di file KMZ.")
                elif not point_list:
                    st.error("❌ Tidak ditemukan point di file KMZ.")
                else:
                    # Buat ID unik berdasarkan FDT dan Polygon_Name
                    unique_poly_identifiers = sorted(list(set((p["FDT"], p["Polygon_Name"]) for p in polygon_list)))
                    poly_id_map = {identifier: idx + 1 for idx, identifier in enumerate(unique_poly_identifiers)}

                    for p in polygon_list:
                        p["Polygon_ID"] = poly_id_map[(p["FDT"], p["Polygon_Name"])]

                    # Spatial Join Manual
                    results = []
                    for pt_data in point_list:
                        pt_geom = pt_data["geometry"]
                        matched_poly_name = "-"
                        matched_poly_id = 9999999
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

                    # Urutkan berdasarkan Polygon_ID
                    final_result = final_result.sort_values(by="Polygon_ID", ascending=True).reset_index(drop=True)
                    final_result["Polygon_ID"] = final_result["Polygon_ID"].apply(lambda x: "" if x == 9999999 else x)

                    # === MENAMBAHKAN KOLOM FORMULA EXCEL KE DETAIL (Kolom A - K) ===
                    g_col, h_col, i_col, j_col, k_col = [], [], [], [], []
                    
                    for idx, row in final_result.iterrows():
                        excel_row = idx + 2
                        prev_row = excel_row - 1
                        next_row = excel_row + 1

                        if idx == 0:
                            g_col.append("=1")
                        else:
                            g_col.append(f'=IF(D{excel_row}<>D{prev_row},1,G{prev_row}+1)')

                        if idx == len(final_result) - 1:
                            h_col.append("=X") 
                        else:
                            h_col.append(f'=IF(D{excel_row}=D{next_row},"","X")')

                        i_col.append(f"=C{excel_row}")
                        j_col.append(f"=B{excel_row}")
                        k_col.append(f"=A{excel_row}")

                    detail_df = final_result[[
                        "Point_Name", "Latitude", "Longitude", "Polygon_Name", "Polygon_ID", "FDT"
                    ]].copy()
                    
                    detail_df["Col_G"] = g_col
                    detail_df["Col_H"] = h_col
                    detail_df["Col_I"] = i_col
                    detail_df["Col_J"] = j_col
                    detail_df["Col_K"] = k_col

                    # === MENYIAPKAN TABEL RINGKASAN (Mulai Kolom M - P) ===
                    valid_data = final_result[final_result["Polygon_ID"] != ""]
                    if not valid_data.empty:
                        summary_df = valid_data.groupby(["Polygon_Name", "Polygon_ID", "FDT"]).size().reset_index(name="Total_HP")
                        summary_df = summary_df.sort_values(by="Polygon_ID", ascending=True).reset_index(drop=True)
                    else:
                        summary_df = pd.DataFrame(columns=["Polygon_Name", "Polygon_ID", "FDT", "Total_HP"])

                    # Samakan jumlah baris antara detail dan summary dengan padding kosong
                    max_rows = max(len(detail_df), len(summary_df))
                    
                    if len(detail_df) < max_rows:
                        pad = pd.DataFrame([[""] * len(detail_df.columns)], columns=detail_df.columns, index=range(max_rows - len(detail_df)))
                        detail_df = pd.concat([detail_df, pad], ignore_index=True)

                    if len(summary_df) < max_rows:
                        pad_sum = pd.DataFrame([[""] * len(summary_df.columns)], columns=summary_df.columns, index=range(max_rows - len(summary_df)))
                        summary_df = pd.concat([summary_df, pad_sum], ignore_index=True)

                    # Gabungkan berdampingan: Detail (A-K) + Kolom Kosong (L) + Summary (M-P)
                    combined_df = detail_df.copy()
                    combined_df[""] = ""  # Kolom L (Pembatas)
                    combined_df["Polygon_Name_Summary"] = summary_df["Polygon_Name"]
                    combined_df["Polygon_ID_Summary"] = summary_df["Polygon_ID"]
                    combined_df["FDT_Summary"] = summary_df["FDT"]
                    combined_df["Total_HP"] = summary_df["Total_HP"]

                    # Ubah header akhir agar sesuai dengan struktur kolom Excel (A s/d P)
                    combined_df.columns = [
                        "Point_Name", "Latitude", "Longitude", "Polygon_Name", "Polygon_ID", "FDT",
                        "Col_G", "Col_H", "Col_I", "Col_J", "Col_K", 
                        "", # Kolom L
                        "Polygon_Name", "Polygon_ID", "FDT", "Total_HP" # Kolom M, N, O, P
                    ]

                    # Simpan ke CSV
                    combined_df.to_csv(output_csv, index=False)

                    st.success("✅ Pemrosesan berhasil! Tabel detail dan ringkasan kini berada dalam satu file sejajar.")
                    
                    # Tampilkan pratinjau di web
                    st.subheader("Pratinjau Hasil Gabungan (Detail A-K & Rekap M-P):")
                    st.dataframe(combined_df.head(15), use_container_width=True)

                    # Tombol Unduh
                    with open(output_csv, "rb") as f:
                        st.download_button(
                            label="📥 Unduh File Hasil (Satu Sheet)",
                            data=f,
                            file_name="hasil_gabungan_detail_dan_rekap.csv",
                            mime="text/csv"
                        )

        except Exception as e:
            st.error(f"Terjadi kesalahan saat memproses file: {e}")
