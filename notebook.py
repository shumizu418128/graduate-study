# -*- coding: utf-8 -*-
# # C:\Program Files\ArcGIS\Pro\bin\Python\envs\arcgispro-py3\python.exe

import arcpy
import requests
import time
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import numpy as np
from scipy.spatial import KDTree, ConvexHull

from aggregation_client import aggregate_points_by_cpp_server

# Check out the ArcGIS Spatial Analyst extension license
arcpy.CheckOutExtension("Spatial")

# スレッドセーフなロック
print_lock = threading.Lock()


def safe_print(*args, **kwargs):
    """スレッドセーフなprint関数"""
    with print_lock:
        print(*args, **kwargs)


# MARK: メイン処理
def main():
    """
    メイン処理
    建物ポイントから最も近い避難所へのルートをOSRMで検索し、
    結果をフィーチャクラスに保存します。
    """
    # --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
    #  ▼▼▼ ユーザー設定項目 ▼▼▼
    # --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---

    # 1. ワークスペースとなるジオデータベースのパス
    project_name = "1030_osaka_shelter2"
    gdb_path = rf"C:\Users\東京電機大学\Documents\ArcGIS\Projects\{project_name}\{project_name}.gdb"

    # 2. 入力フィーチャクラス名 (UTM座標系などを想定)
    building_fc_name = "建築物_FeatureToPoint_Clip"
    shelter_fc_name = "osaka_shelter"

    # 3. 出力フィーチャクラス名 (新規作成されます)
    output_fc_name = "OSRM_Routes_Optimized"

    # 4. OSRMサーバーのURL (ローカルのDockerサーバーを指定)
    osrm_url = "http://localhost:5000"

    # 5. 建物集約の半径 (メートル単位)
    aggregation_radius_meters = 150

    # 6. 検索対象とする近傍の避難所数
    num_closest_shelters = 3

    # 7. 並列処理の同時実行スレッド数 (OSRMサーバーの性能に応じて調整)
    max_workers = 10

    # --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---
    # ▲▲▲ ユーザー設定ここまで ▲▲▲
    # --- --- --- --- --- --- --- --- --- --- --- --- --- --- ---

    try:
        # --- 1. 環境設定 ---
        arcpy.env.workspace = gdb_path
        arcpy.env.overwriteOutput = True
        safe_print(f"ワークスペースを {gdb_path} に設定しました。")

        # --- 2. 前処理: 座標変換 (WGS84へ) ---
        wgs84_sr = arcpy.SpatialReference(4326)

        # building_fc_name の座標系を取得
        desc_building = arcpy.Describe(building_fc_name)
        building_sr = desc_building.spatialReference
        safe_print(f"建物フィーチャクラスの座標系: {building_sr.name} (タイプ: {building_sr.type})")

        # 座標系に応じて処理を分岐
        if building_sr.factoryCode == 4326:  # 既にWGS84の場合
            safe_print(f"'{building_fc_name}' は既にWGS84座標系です。変換をスキップします。")
            building_fc_wgs84 = building_fc_name
        else:
            # WGS84でない場合は変換を実行
            building_fc_wgs84 = f"{building_fc_name}_WGS84"
            if arcpy.Exists(building_fc_wgs84):
                safe_print(f"'{building_fc_wgs84}' は既に存在します。再利用します。")
            else:
                safe_print(f"'{building_fc_name}' をWGS84に変換しています...")
                arcpy.management.Project(building_fc_name, building_fc_wgs84, wgs84_sr)

        # shelter_fc_name の座標系を取得
        desc_shelter = arcpy.Describe(shelter_fc_name)
        shelter_sr = desc_shelter.spatialReference
        safe_print(f"避難所フィーチャクラスの座標系: {shelter_sr.name} (タイプ: {shelter_sr.type})")

        # 座標系に応じて処理を分岐
        if shelter_sr.factoryCode == 4326:  # 既にWGS84の場合
            safe_print(f"'{shelter_fc_name}' は既にWGS84座標系です。変換をスキップします。")
            shelter_fc_wgs84 = shelter_fc_name
        else:
            # WGS84でない場合は変換を実行
            shelter_fc_wgs84 = f"{shelter_fc_name}_WGS84"
            if arcpy.Exists(shelter_fc_wgs84):
                safe_print(f"'{shelter_fc_wgs84}' は既に存在します。再利用します。")
            else:
                safe_print(f"'{shelter_fc_name}' をWGS84に変換しています...")
                arcpy.management.Project(shelter_fc_name, shelter_fc_wgs84, wgs84_sr)
        safe_print("座標変換が完了しました。")

        # --- 3. データ読み込み (WGS84座標) ---
        safe_print("建物ポイント(WGS84)をメモリに読み込んでいます...")
        building_coords_wgs84 = get_coords_dict_from_fc(building_fc_wgs84)

        safe_print("避難所の座標をメモリに読み込んでいます...")
        shelter_coords_dict = get_coords_dict_from_fc(shelter_fc_wgs84)
        safe_print(f"避難所の数: {len(shelter_coords_dict)}")

        # --- 4. 建物ポイントの集約 (最適化実装) ---
        safe_print(f"建物ポイントを半径 {aggregation_radius_meters}m で集約しています (最適化実装)...")
        # NumPy版（最高速）
        # aggregated_building_coords = aggregate_points_by_grid_max_speed(building_coords_wgs84, aggregation_radius_meters)
        # C++版
        aggregated_building_coords = aggregate_points_by_cpp_server(building_coords_wgs84, aggregation_radius_meters)
        total_aggregated_buildings = len(aggregated_building_coords)
        safe_print(f"建物の集約が完了しました。代表ポイント数: {total_aggregated_buildings}")

        # --- 5. 近傍避難所の特定 (Python実装) ---
        safe_print(f"各建物代表ポイントに最も近い {num_closest_shelters} 件の避難所を検索しています (Python実装)...")
        near_dict = find_closest_shelters(aggregated_building_coords, shelter_coords_dict, num_closest_shelters, max_workers)

        # --- OSRMサーバーの接続テスト ---
        safe_print(f"OSRMサーバー ({osrm_url}) の接続をテストしています...")
        max_retries = 1000  # 非常に大きな数に設定
        retry_delay = 5  # 5秒待機

        for attempt in range(max_retries):
            try:
                # タイムアウトをNoneに設定して無限に待機
                test_response = requests.get(f"{osrm_url}/route/v1/driving/139.7670,35.6814;139.7671,35.6815", timeout=None)
                if test_response.status_code == 200:
                    safe_print("OSRMサーバーに正常に接続できました。")
                    break
                else:
                    safe_print(f"OSRMサーバーの応答が異常です。ステータスコード: {test_response.status_code}")
                    break
            except requests.exceptions.ConnectionError as e:
                safe_print(f"OSRMサーバー接続エラー (試行 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    safe_print(f"{retry_delay}秒後に再試行します...")
                    time.sleep(retry_delay)
                else:
                    safe_print(f"OSRMサーバーに接続できません（{max_retries}回試行後）: {e}")
                    safe_print("ルート検索はスキップされますが、集約ポイントは保存されます。")
            except Exception as e:
                safe_print(f"OSRMサーバーに接続できません: {e}")
                safe_print("ルート検索はスキップされますが、集約ポイントは保存されます。")
                break


        # --- 集約建物ポイントの新規レイヤー作成 ---
        agg_points_fc_name = "Aggregated_Buildings"
        safe_print(f"集約建物ポイントフィーチャクラス '{agg_points_fc_name}' を作成しています...")
        if arcpy.Exists(agg_points_fc_name):
            arcpy.management.Delete(agg_points_fc_name)

        arcpy.management.CreateFeatureclass(
            gdb_path,
            agg_points_fc_name,
            "POINT",
            spatial_reference=wgs84_sr
        )
        safe_print(f"集約建物ポイントフィーチャクラス '{agg_points_fc_name}' の作成が完了しました。")

        # フィールドを追加
        arcpy.management.AddField(agg_points_fc_name, "Agg_OID", "LONG", field_alias="集約建物OID")
        arcpy.management.AddField(agg_points_fc_name, "Nearest", "LONG", field_alias="最寄り避難所OID")
        arcpy.management.AddField(agg_points_fc_name, "Drtn_sec", "DOUBLE", field_alias="所要時間(秒)")
        arcpy.management.AddField(agg_points_fc_name, "Dstnc_m", "DOUBLE", field_alias="距離(m)")
        safe_print("集約建物ポイントフィーチャクラスのフィールドの追加が完了しました。")

        # --- 6. 出力フィーチャクラスの作成 ---
        safe_print(f"出力フィーチャクラス '{output_fc_name}' を作成しています...")
        if arcpy.Exists(output_fc_name):
            arcpy.management.Delete(output_fc_name)
        arcpy.management.CreateFeatureclass(
            gdb_path,
            output_fc_name,
            "POLYLINE",
            spatial_reference=wgs84_sr
        )
        arcpy.management.AddField(output_fc_name, "Agg_OID", "LONG", field_alias="集約建物OID")  # 集約建物OID
        arcpy.management.AddField(output_fc_name, "Shltr_OID", "LONG", field_alias="避難所OID")  # 避難所OID
        arcpy.management.AddField(output_fc_name, "Drtn_sec", "DOUBLE", field_alias="所要時間(秒)")  # 所要時間(秒)
        arcpy.management.AddField(output_fc_name, "Dstnc_m", "DOUBLE", field_alias="距離(m)")  # 距離(m)

        # --- 7. ルート検索と保存 & 集約ポイント属性保存 (最適化バッチ並列処理版) ---
        safe_print(f"最適化バッチ並列処理を開始します（最大 {max_workers} スレッド）...")

        # 処理対象のタスクリストを作成
        tasks = []
        for agg_bldg_oid, agg_bldg_coord in aggregated_building_coords.items():
            nearby_shelter_oids = near_dict.get(agg_bldg_oid)
            if nearby_shelter_oids:
                tasks.append((agg_bldg_oid, agg_bldg_coord, nearby_shelter_oids))

        # バッチサイズを調整（OSRMサーバーの負荷を考慮）
        batch_size = min(20, max(1, len(tasks) // max_workers))
        batches = [tasks[i:i + batch_size] for i in range(0, len(tasks), batch_size)]

        # 並列処理の実行
        route_rows = []
        successful_routes = 0
        skipped_routes = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # バッチを並列実行
            future_to_batch = {
                executor.submit(process_batch_routes, batch, shelter_coords_dict, osrm_url): batch
                for batch in batches
            }

            # 結果を収集
            with tqdm(total=len(tasks), desc="バッチ処理中（並列）", unit="件") as pbar:
                for future in as_completed(future_to_batch):
                    batch_results = future.result()

                    for result in batch_results:
                        agg_bldg_oid = result['agg_bldg_oid']
                        agg_bldg_coord = result['agg_bldg_coord']

                        if result['success']:
                            # 成功した場合
                            successful_routes += 1

                            # ルート情報を一時リストに格納
                            geom = arcpy.AsShape(result['route_info']['geometry'])
                            row_data = (
                                geom,
                                agg_bldg_oid,
                                result['nearest_shltr']['oid'],
                                result['route_info']['duration'],
                                result['route_info']['distance']
                            )
                            route_rows.append(row_data)

                        else:
                            # 失敗した場合
                            skipped_routes += 1
                            if result['error']:
                                safe_print(f"建物OID {agg_bldg_oid} の処理中にエラー: {result['error']}")

                        # 進捗表示を更新
                        pbar.set_postfix({
                            '成功': successful_routes,
                            'スキップ': skipped_routes,
                            '成功率': f"{(successful_routes / (successful_routes + skipped_routes) * 100):.1f}%" if (successful_routes + skipped_routes) > 0 else "0.0%"
                        })
                        pbar.update(1)

        # 集約ポイントレイヤーにデータを保存
        safe_print("集約ポイントレイヤーにデータを保存しています...")
        safe_print(f"保存対象の集約ポイント数: {len(aggregated_building_coords)}")

        try:
            agg_cursor = arcpy.da.InsertCursor(agg_points_fc_name, ["SHAPE@XY", "Agg_OID", "Nearest", "Drtn_sec", "Dstnc_m"])

            # 成功したルートの情報を辞書に整理
            successful_routes_dict = {}
            for route_row in route_rows:
                agg_bldg_oid = route_row[1]  # Agg_OID
                successful_routes_dict[agg_bldg_oid] = {
                    'shltr_oid': route_row[2],  # Shltr_OID
                    'duration': route_row[3],   # Drtn_sec
                    'distance': route_row[4]    # Dstnc_m
                }

            # 全ての集約ポイントを保存
            saved_count = 0
            for agg_bldg_oid, agg_bldg_coord in aggregated_building_coords.items():
                try:
                    if agg_bldg_oid in successful_routes_dict:
                        # 成功したルートがある場合
                        route_data = successful_routes_dict[agg_bldg_oid]
                        agg_cursor.insertRow([
                            (agg_bldg_coord['lon'], agg_bldg_coord['lat']),
                            agg_bldg_oid,
                            route_data['shltr_oid'],
                            route_data['duration'],
                            route_data['distance']
                        ])
                    else:
                        # ルート検索が失敗した場合
                        agg_cursor.insertRow([
                            (agg_bldg_coord['lon'], agg_bldg_coord['lat']),
                            agg_bldg_oid,
                            None,  # Nearest
                            None,  # Drtn_sec
                            None   # Dstnc_m
                        ])
                    saved_count += 1
                except Exception as e:
                    safe_print(f"集約ポイント {agg_bldg_oid} の保存中にエラー: {e}")
                    continue

            del agg_cursor
            safe_print(f"集約ポイントの保存が完了しました。保存件数: {saved_count}")

        except Exception as e:
            safe_print(f"集約ポイント保存中に致命的なエラー: {e}")

        # フィーチャクラスの存在確認
        if arcpy.Exists(agg_points_fc_name):
            desc = arcpy.Describe(agg_points_fc_name)
            safe_print(f"フィーチャクラス '{agg_points_fc_name}' が正常に作成されました。")
            safe_print(f"  フィーチャ数: {arcpy.management.GetCount(agg_points_fc_name)[0]}")
        else:
            safe_print(f"フィーチャクラス '{agg_points_fc_name}' が見つかりません。")

        safe_print(f"集約ポイントの保存が完了しました。")
        safe_print(f"  成功: {successful_routes} 件")
        safe_print(f"  スキップ: {skipped_routes} 件")
        safe_print(f"  合計: {successful_routes + skipped_routes} 件")

        # ルート情報をまとめて出力フィーチャクラスに保存
        if route_rows:
            safe_print(f"ルート情報を出力フィーチャクラスに保存しています... ({len(route_rows)} 件)")
            insert_cursor = arcpy.da.InsertCursor(output_fc_name, ["SHAPE@", "Agg_OID", "Shltr_OID", "Drtn_sec", "Dstnc_m"])
            for row_data in route_rows:
                insert_cursor.insertRow(row_data)
            del insert_cursor
            safe_print("ルート情報の保存が完了しました。")
        else:
            safe_print("保存するルート情報がありませんでした。")

        safe_print("\n全ての処理が完了しました。")
        safe_print(f"作成されたフィーチャクラス:")
        safe_print(f"  - {agg_points_fc_name}: 集約建物ポイント")
        if route_rows:
            safe_print(f"  - {output_fc_name}: ルート情報")

    except arcpy.ExecuteError:
        safe_print(arcpy.GetMessages(2))


# MARK: ポイント集約
def aggregate_points_by_grid_max_speed(points_dict, radius_m):
    """最高速ポイント集約 - NumPy Advanced Indexing実装（極限最適化版）"""
    points_data = list(points_dict.values())
    if not points_data:
        return {}

    safe_print(f"集約対象ポイント数: {len(points_data)}")

    # NumPy配列として一括変換（最適化）
    coords = np.array([[p['lon'], p['lat']] for p in points_data], dtype=np.float64)

    # 参照点（重心）
    ref_point = np.mean(coords, axis=0)
    ref_lon, ref_lat = ref_point[0], ref_point[1]

    # デカルト座標変換（完全ベクトル化）
    R = 6371000.0
    ref_lat_rad = np.radians(ref_lat)

    xy = np.empty((len(coords), 2), dtype=np.float64)
    xy[:, 0] = R * np.radians(coords[:, 0] - ref_lon) * np.cos(ref_lat_rad)
    xy[:, 1] = R * np.radians(coords[:, 1] - ref_lat)

    # グリッドインデックス（完全ベクトル化）
    grid_size = radius_m * 2.0
    grid_indices = np.floor(xy / grid_size).astype(np.int32)

    # グリッドを一意のIDに変換（より効率的）
    grid_ids = grid_indices[:, 0] * 100000 + grid_indices[:, 1]

    # ユニークなグリッドを高速取得
    unique_ids, inverse_indices = np.unique(grid_ids, return_inverse=True)

    # 最高速集約：凸包を使用した重心計算
    aggregated_points = {}

    for i in tqdm(range(len(unique_ids)), desc="集約処理"):
        mask = inverse_indices == i
        group_coords = coords[mask]

        # 凸包の重心を計算（図形の内側に重心が来るように）
        if len(group_coords) >= 3:
            try:
                # 凸包を計算
                hull = ConvexHull(group_coords)
                # 凸包の頂点座標の重心を計算
                hull_points = group_coords[hull.vertices]
                centroid = np.mean(hull_points, axis=0)
            except Exception:
                # 凸包計算に失敗した場合は算術平均を使用
                centroid = np.mean(group_coords, axis=0)
        else:
            # 点数が3未満の場合は算術平均を使用
            centroid = np.mean(group_coords, axis=0)

        aggregated_points[i + 1] = {
            'oid': i + 1,
            'lon': centroid[0],
            'lat': centroid[1]
        }

    return aggregated_points


# MARK: 近傍検索
def find_closest_shelters(aggregated_points, shelters, num_closest, max_workers):
    """KDTreeを使った高速近傍検索"""

    # 避難所の座標を配列に変換（度数をラジアンに変換）
    shelter_list = list(shelters.values())
    shelter_coords = np.array([[s['lat'], s['lon']] for s in shelter_list])
    shelter_coords_rad = np.radians(shelter_coords)

    # 球面座標を3D直交座標に変換（より正確な距離計算のため）
    x = np.cos(shelter_coords_rad[:, 0]) * np.cos(shelter_coords_rad[:, 1])
    y = np.cos(shelter_coords_rad[:, 0]) * np.sin(shelter_coords_rad[:, 1])
    z = np.sin(shelter_coords_rad[:, 0])
    shelter_3d = np.column_stack([x, y, z])

    # KDTreeを構築
    tree = KDTree(shelter_3d)

    near_dict = {}
    for agg_oid, agg_point in aggregated_points.items():
        # 集約ポイントも3D座標に変換
        lat_rad, lon_rad = np.radians([agg_point['lat'], agg_point['lon']])
        point_x = np.cos(lat_rad) * np.cos(lon_rad)
        point_y = np.cos(lat_rad) * np.sin(lon_rad)
        point_z = np.sin(lat_rad)

                # 最近傍検索
        distances, indices = tree.query([point_x, point_y, point_z], k=num_closest)

        # 単一の結果の場合は配列に変換
        if np.isscalar(indices):
            indices = np.array([indices])
        elif not isinstance(indices, np.ndarray):
            indices = np.array(indices)

        closest_shelter_oids = [shelter_list[int(i)]['oid'] for i in indices]
        near_dict[agg_oid] = closest_shelter_oids

    return near_dict


# MARK: データ読み込み
def get_coords_dict_from_fc(feature_class):
    """メモリ効率的なデータ読み込み"""

    coords_dict = {}
    chunk_size = 10000

    with arcpy.da.SearchCursor(feature_class, ["OID@", "SHAPE@XY"]) as cursor:
        chunk = []
        for row in cursor:
            chunk.append(row)
            if len(chunk) >= chunk_size:
                # チャンクを処理
                for oid, (lon, lat) in chunk:
                    coords_dict[oid] = {'oid': oid, 'lon': lon, 'lat': lat}
                chunk = []

        # 残りを処理
        for oid, (lon, lat) in chunk:
            coords_dict[oid] = {'oid': oid, 'lon': lon, 'lat': lat}

    return coords_dict


# MARK: ルート処理
def process_batch_routes(batch_tasks, shelter_coords_dict, osrm_url):
    """バッチでルート処理"""
    results = []

    # バッチサイズが大きすぎる場合は分割処理
    if len(batch_tasks) > 10:
        # 大きなバッチは個別処理にフォールバック
        for agg_bldg_oid, agg_bldg_coord, nearby_shelter_oids in batch_tasks:
            result = process_single_route(agg_bldg_oid, agg_bldg_coord, nearby_shelter_oids, shelter_coords_dict, osrm_url)
            results.append(result)
        return results

    # 小さなバッチは個別処理で十分効率的
    for agg_bldg_oid, agg_bldg_coord, nearby_shelter_oids in batch_tasks:
        result = process_single_route(agg_bldg_oid, agg_bldg_coord, nearby_shelter_oids, shelter_coords_dict, osrm_url)
        results.append(result)

    return results


# MARK: 最短の避難所検索
def find_closest_by_table(source_building, target_shelters, osrm_url):
    """OSRMのTableサービスを使い、3つの避難所から最も近い施設を見つける"""

    # 座標の文字列を作成: "lon1,lat1;lon2,lat2;..."
    shelter_coords_str = ";".join([f"{s['lon']},{s['lat']}" for s in target_shelters])
    locations_str = f"{source_building['lon']},{source_building['lat']};{shelter_coords_str}"

    # API URLを作成（sources=0 は最初の座標=建物をソースとすることを意味する、徒歩モード "walking" を使用）
    api_url = f"{osrm_url}/table/v1/walking/{locations_str}?sources=0&annotations=duration"

    # 無限に待機するための再試行ロジック
    max_retries = 10000  # 非常に大きな数に設定

    for attempt in range(max_retries):
        try:
            # タイムアウトをNoneに設定して無限に待機
            response = requests.get(api_url, timeout=None)
            response.raise_for_status()
            data = response.json()

            if data['code'] != 'Ok' or not data.get('durations'):
                safe_print(f"OSRM Table API Error: {data.get('message', 'No message')}")
                return None, None

            durations = data['durations'][0]
            min_duration = float('inf')
            closest_shelter_index = -1

            # 最初の要素は建物自身(0)なのでスキップし、避難所との所要時間のみをチェック
            for idx, duration in enumerate(durations[1:]):
                if duration is not None and duration < min_duration:
                    min_duration = duration
                    closest_shelter_index = idx

            if closest_shelter_index == -1:
                return None, None

            return target_shelters[closest_shelter_index], min_duration

        except requests.exceptions.ConnectionError as e:
            continue
    # ループを抜けた場合にも必ずタプルで返す
    return None, None


# MARK: ルート詳細
def get_route_geometry(source_building, target_shelter, osrm_url):
    """OSRMのRouteサービスを使い、2点間の経路ジオメトリと詳細情報を取得"""

    coords_str = f"{source_building['lon']},{source_building['lat']};{target_shelter['lon']},{target_shelter['lat']}"
    api_url = f"{osrm_url}/route/v1/walking/{coords_str}?overview=full&geometries=geojson"

    # 無限に待機するための再試行ロジック
    max_retries = 10000  # 非常に大きな数に設定

    for attempt in range(max_retries):
        try:
            # タイムアウトをNoneに設定して無限に待機
            response = requests.get(api_url, timeout=None)
            response.raise_for_status()
            data = response.json()

            if data['code'] == 'Ok' and data.get('routes'):
                return data['routes'][0] # 距離、時間、ジオメトリを含むルートオブジェクトを返す
            else:
                safe_print(f"OSRM Route API Error: {data.get('message', 'No message')}")
                return None

        except requests.exceptions.ConnectionError as e:
            continue  # つながるまでやれ


# MARK: 単一ルート検索
def process_single_route(agg_bldg_oid, agg_bldg_coord, nearby_shelter_oids, shelter_coords_dict, osrm_url):
    """単一のルート検索処理を実行する関数（並列処理用）"""
    try:
        # 近傍避難所の座標リストを作成
        target_shelters = [shelter_coords_dict[oid] for oid in nearby_shelter_oids if oid in shelter_coords_dict]
        if not target_shelters:
            return {
                'agg_bldg_oid': agg_bldg_oid,
                'agg_bldg_coord': agg_bldg_coord,
                'success': False,
                'nearest_shltr': None,
                'route_info': None,
                'error': '避難所座標が見つかりません'
            }

        # Tableサービスで最も近い避難所を特定
        closest_shelter, min_duration = find_closest_by_table(agg_bldg_coord, target_shelters, osrm_url)
        if closest_shelter is None:
            return {
                'agg_bldg_oid': agg_bldg_oid,
                'agg_bldg_coord': agg_bldg_coord,
                'success': False,
                'nearest_shltr': None,
                'route_info': None,
                'error': 'OSRM Tableサービスが失敗しました'
            }

        # Routeサービスで経路ジオメトリと詳細情報を取得
        route_info = get_route_geometry(agg_bldg_coord, closest_shelter, osrm_url)
        if not route_info:
            return {
                'agg_bldg_oid': agg_bldg_oid,
                'agg_bldg_coord': agg_bldg_coord,
                'success': False,
                'nearest_shltr': closest_shelter,
                'route_info': None,
                'error': 'OSRM Routeサービスが失敗しました'
            }

        return {
            'agg_bldg_oid': agg_bldg_oid,
            'agg_bldg_coord': agg_bldg_coord,
            'success': True,
            'nearest_shltr': closest_shelter,
            'route_info': route_info,
            'error': None
        }

    except Exception as e:
        return {
            'agg_bldg_oid': agg_bldg_oid,
            'agg_bldg_coord': agg_bldg_coord,
            'success': False,
            'nearest_shltr': None,
            'route_info': None,
            'error': str(e)
        }


if __name__ == '__main__':
    # 実行には tqdm ライブラリが必要です
    # pip install tqdm
    start_time = time.time()
    main()
    end_time = time.time()
    elapsed = end_time - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)
    safe_print(f"総処理時間: {minutes}分{seconds:02d}秒")
