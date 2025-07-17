# C++ポイント集約サーバー

高速なポイント集約処理を行うC++ベースのHTTPサーバーです。ArcGISの建物ポイントデータを効率的に集約するために設計されています。

## 構成ファイル

```
cpp_aggregation_server/
├── main.cpp              # メインのC++サーバーコード
├── CMakeLists.txt        # CMakeビルド設定
├── Dockerfile            # Dockerイメージ設定
├── docker-compose.yml    # Dockerサービス設定
└── README.md            # このファイル
```

# cpp_aggregation_server 処理の流れ

このサーバーは、HTTP POSTで受け取った地理座標データ（緯度・経度）を指定した半径でグループ化（クラスタリング）し、各グループの重心座標を返すC++製の高速集約サーバーです。

## 主な処理の流れ（main.cpp）

1. **HTTPサーバー起動**
   - `httplib`ライブラリを用いてサーバーを起動。
   - `/aggregate`エンドポイントでPOSTリクエストを受け付ける。

2. **リクエスト受信・パース**
   - JSON形式で`points`（座標リスト）と`radius`（集約半径[m]）を受信。
   - 各ポイントは`lon`（経度）, `lat`（緯度）, `oid`（ID）を持つ。

3. **地理座標→デカルト座標変換**
   - 計算の高速化のため、全ポイントを地理座標（緯度・経度）からデカルト座標（x, y）に変換。
   - 変換時の基準点（重心）も計算。

4. **空間インデックス構築**
   - グリッドベースの空間インデックス（SpatialIndex）を構築。
   - 各点をグリッドに割り当て、近傍探索を高速化。

5. **グループ化処理**
   - 各点について、未処理の点のみを対象に、指定半径内の候補点を空間インデックスから取得。
   - 距離判定し、半径内の点をグループ化。
   - グループ内の全点を処理済みとする。

6. **重心計算**
   - グループ点が3点以上なら凸包を計算し、その重心を算出。
   - それ以外は単純な重心を算出。
   - デカルト座標の重心を地理座標に逆変換。

7. **レスポンス生成**
   - 各グループの重心座標（`lon`, `lat`）とグループID（`oid`）をJSONで返却。
   - 入力点数・出力点数も含めて返す。

## エンドポイント

- `POST /aggregate`
  - リクエスト: `{ "points": [{"lon":..., "lat":..., "oid":...}, ...], "radius": ... }`
  - レスポンス: `{ "status": "success", "aggregated_points": {...}, "input_count":..., "output_count":... }`

- `GET /health`
  - サーバーヘルスチェック用

## 依存ライブラリ
- [cpp-httplib](https://github.com/yhirose/cpp-httplib)
- [nlohmann/json](https://github.com/nlohmann/json)

## ビルド・実行方法
CMakeやg++でビルドし、8080番ポートでサーバーが起動します。

---

- Docker
- Docker Compose

または

- CMake 3.16+
- GCC 7+ or Clang 6+
- C++17対応コンパイラ

## インストール・起動

### Dockerを使用する場合（推奨）

1. サーバーディレクトリに移動:
```bash
cd cpp_aggregation_server
```

2. Dockerコンテナをビルド・起動:
```bash
docker-compose up --build
```

Dockerの起動のみ
```bash
docker-compose up
```

3. サーバーが起動したことを確認:
```bash
curl http://localhost:8080/health
```

### 手動ビルドの場合

1. 依存関係をインストール（Ubuntu例）:
```bash
sudo apt-get update
sudo apt-get install build-essential cmake git
```

2. ビルド:
```bash
mkdir build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)
```

3. 実行:
```bash
./aggregation_server
```

## API仕様

### エンドポイント

#### GET /health
ヘルスチェック用エンドポイント

**レスポンス:**
```json
{
  "status": "ok"
}
```

#### POST /aggregate
ポイント集約処理エンドポイント

**リクエスト:**
```json
{
  "radius": 100.0,
  "points": [
    {
      "oid": 1,
      "lon": 139.7671,
      "lat": 35.6814
    },
    {
      "oid": 2,
      "lon": 139.7672,
      "lat": 35.6815
    }
  ]
}
```

**パラメータ:**
- `radius`: 集約半径（メートル単位）
- `points`: 集約対象のポイント配列
  - `oid`: ポイントのオブジェクトID
  - `lon`: 経度（WGS84）
  - `lat`: 緯度（WGS84）

**レスポンス:**
```json
{
  "status": "success",
  "input_count": 2,
  "output_count": 1,
  "aggregated_points": {
    "1": {
      "oid": 1,
      "lon": 139.76715,
      "lat": 35.68145
    }
  }
}
```

## Pythonクライアント例

既存のPythonコードから集約サーバーを呼び出す例:

```python
import requests
import json

def call_cpp_aggregation_server(points_dict, radius_meters, server_url="http://localhost:8080"):
    """
    C++集約サーバーを呼び出してポイント集約を実行

    Args:
        points_dict: {oid: {'oid': oid, 'lon': lon, 'lat': lat}} 形式の辞書
        radius_meters: 集約半径（メートル）
        server_url: C++サーバーのURL

    Returns:
        集約結果の辞書
    """
    # データを変換
    points_list = list(points_dict.values())

    request_data = {
        "radius": radius_meters,
        "points": points_list
    }

    try:
        response = requests.post(
            f"{server_url}/aggregate",
            json=request_data,
            timeout=300
        )
        response.raise_for_status()

        result = response.json()

        if result["status"] == "success":
            # 結果をPythonコードに合わせた形式に変換
            aggregated_points = {}
            for key, point_data in result["aggregated_points"].items():
                aggregated_points[int(key)] = point_data

            print(f"集約完了: {result['input_count']} → {result['output_count']} ポイント")
            return aggregated_points
        else:
            raise Exception(f"集約サーバーエラー: {result.get('message', 'Unknown error')}")

    except requests.exceptions.RequestException as e:
        print(f"集約サーバーとの通信エラー: {e}")
        raise
```

## パフォーマンス

C++実装により、Pythonの実装と比較して以下のパフォーマンス向上が期待できます:

- **処理速度**: 5-10倍高速
- **メモリ使用量**: 50-70%削減
- **スケーラビリティ**: 100万ポイント以上の処理に対応

## トラブルシューティング

### よくある問題

1. **ポート8080が既に使用されている**
   ```bash
   # docker-compose.ymlのポート設定を変更
   ports:
     - "8081:8080"  # 8081ポートを使用
   ```

2. **メモリ不足エラー**
   - Dockerのメモリ制限を増やす
   - バッチサイズを小さくしてデータを分割処理

3. **ビルドエラー**
   - CMakeバージョンを確認（3.16+が必要）
   - C++17対応コンパイラを使用

### ログの確認

```bash
# Dockerコンテナのログを確認
docker-compose logs -f aggregation-server

# コンテナ内でのデバッグ
docker exec -it cpp-aggregation-server /bin/bash
```

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。

## 貢献

バグ報告や機能要望がありましたら、GitHubのIssueまでお願いします。