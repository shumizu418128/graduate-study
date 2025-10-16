#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import time
from typing import Dict, Any


def call_cpp_aggregation_server(points_dict: Dict[int, Dict[str, Any]],
                               radius_meters: float,
                               server_url: str = "http://localhost:8080") -> Dict[int, Dict[str, Any]]:
    """
    C++集約サーバーを呼び出してポイント集約を実行

    Args:
        points_dict: {oid: {'oid': oid, 'lon': lon, 'lat': lat}} 形式の辞書
        radius_meters: 集約半径（メートル）
        server_url: C++サーバーのURL

    Returns:
        集約結果の辞書 (元のPythonコードと同じ形式)

    Raises:
        requests.exceptions.RequestException: サーバーとの通信エラー
        Exception: サーバー側のエラー
    """
    start_time = time.time()

    print(f"C++集約サーバーにリクエストを送信中... ({len(points_dict)} ポイント)")

    # データの検証とフィルタリング
    valid_points = []
    invalid_count = 0

    for p in points_dict.values():
        # None値や無効な値をチェック
        if (p.get("lon") is not None and p.get("lat") is not None and p.get("oid") is not None and
            isinstance(p["lon"], (int, float)) and isinstance(p["lat"], (int, float)) and
            isinstance(p["oid"], (int, float))):
            valid_points.append({
                "lon": float(p["lon"]),
                "lat": float(p["lat"]),
                "oid": int(p["oid"])
            })
        else:
            invalid_count += 1
            print(f"無効なポイントをスキップ: {p}")

    if invalid_count > 0:
        print(f"警告: {invalid_count} 個の無効なポイントをスキップしました")

    print(f"有効なポイント数: {len(valid_points)}")
    points_list = valid_points

    request_data = {
        "radius": radius_meters,
        "points": points_list
    }

    # デバッグ: リクエストデータの一部を表示
    print(f"リクエストデータ: radius={radius_meters}, points数={len(points_list)}")
    if points_list:
        print(f"最初のポイント例: {points_list[0]}")
        print(f"最後のポイント例: {points_list[-1]}")

    try:
        # サーバーにリクエストを送信（json=パラメータを使用）
        response = requests.post(
            f"{server_url}/aggregate",
            json=request_data,
            timeout=300  # 5分でタイムアウト
        )
        response.raise_for_status()

        result = response.json()

        if result["status"] == "success":
            # 結果をPythonコードに合わせた形式に変換
            aggregated_points = {}
            for key, point_data in result["aggregated_points"].items():
                aggregated_points[int(key)] = point_data

            end_time = time.time()
            processing_time = end_time - start_time

            print(f"C++集約完了: {result['input_count']} → {result['output_count']} ポイント")
            print(f"処理時間: {processing_time:.2f}秒")

            return aggregated_points
        else:
            raise Exception(f"集約サーバーエラー: {result.get('message', 'Unknown error')}")

    except requests.exceptions.ConnectionError:
        print(f"エラー: C++集約サーバー ({server_url}) に接続できません。")
        raise
    except requests.exceptions.Timeout:
        print("エラー: C++集約サーバーの応答がタイムアウトしました。")
        raise
    except requests.exceptions.RequestException as e:
        print(f"集約サーバーとの通信エラー: {e}")
        # レスポンスの内容があれば表示
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_content = e.response.text
                print(f"サーバーエラーレスポンス: {error_content}")
            except:
                print("サーバーエラーレスポンスの読み取りに失敗")
        raise


def check_server_health(server_url: str = "http://localhost:8080") -> bool:
    """
    C++集約サーバーのヘルスチェックを実行

    Args:
        server_url: C++サーバーのURL

    Returns:
        サーバーが正常に動作している場合True
    """
    try:
        response = requests.get(f"{server_url}/health", timeout=5)
        response.raise_for_status()
        result = response.json()
        return result.get("status") == "ok"
    except Exception:
        return False


def aggregate_points_by_cpp_server(points_dict: Dict[int, Dict[str, Any]],
                                 radius_meters: float) -> Dict[int, Dict[str, Any]]:
    """
    notebook.pyのaggregate_points_by_grid_max_speed関数の置き換え用関数

    この関数は、既存のPythonコードから直接呼び出すことができます。
    関数シグネチャと戻り値の形式は元の関数と互換性があります。

    Args:
        points_dict: ポイント辞書
        radius_meters: 集約半径（メートル）

    Returns:
        集約結果の辞書
    """
    server_url = "http://localhost:8080"

    # サーバーのヘルスチェック
    if not check_server_health(server_url):
        raise Exception("C++集約サーバーが利用できません")

    # C++集約サーバーを呼び出して集約処理を実行
    return call_cpp_aggregation_server(points_dict, radius_meters, server_url)


def test_aggregation_server():
    """
    集約サーバーのテスト用関数
    """
    print("C++ポイント集約サーバーのテストを開始...")

    # テストデータ
    test_points = {
        1: {'oid': 1, 'lon': 139.7671, 'lat': 35.6814},
        2: {'oid': 2, 'lon': 139.7672, 'lat': 35.6815},
        3: {'oid': 3, 'lon': 139.7673, 'lat': 35.6816},
        4: {'oid': 4, 'lon': 139.7674, 'lat': 35.6817},
        5: {'oid': 5, 'lon': 139.7675, 'lat': 35.6818},
    }

    radius = 100.0  # 100メートル

    try:
        # ヘルスチェック
        print("1. ヘルスチェック...")
        if check_server_health():
            print("   ✓ サーバーは正常に動作しています")
        else:
            print("   ✗ サーバーのヘルスチェックに失敗しました")
            return

        # 集約処理のテスト
        print("2. 集約処理のテスト...")
        result = aggregate_points_by_cpp_server(test_points, radius)

        print("   ✓ 集約処理が正常に完了しました")
        print(f"   入力ポイント数: {len(test_points)}")
        print(f"   出力ポイント数: {len(result)}")
        print("   結果:")
        for oid, point in result.items():
            print(f"     OID {oid}: ({point['lon']:.6f}, {point['lat']:.6f})")

    except Exception as e:
        print(f"   ✗ テストに失敗しました: {e}")


if __name__ == "__main__":
    # テストを実行
    test_aggregation_server()

# 既存のnotebook.pyでの使用例:

# 1. 元の関数の置き換え
# from python_client_example import aggregate_points_by_cpp_server

# 2. main()関数内で以下のように変更:
# aggregated_building_coords = aggregate_points_by_cpp_server(building_coords_wgs84, aggregation_radius_meters)

# 3. または、直接呼び出し:
# from python_client_example import call_cpp_aggregation_server
# result = call_cpp_aggregation_server(points_dict, radius_meters)
