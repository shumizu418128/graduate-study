# OSRM処理最適化ツール

関東地方のOSMデータを使用したOSRM（Open Source Routing Machine）の処理を最適化するためのツールです。

## 🚀 最適化のポイント

- **固定設定**: 安定した処理パフォーマンス
- **メモリ最適化**: 24GBメモリ制限で高速処理
- **スレッド最適化**: 4スレッドで効率的な並列処理
- **自動化**: 手動コマンド入力不要
- **安全性**: エラーハンドリング付き

## 📋 必要なファイル

- `kanto-latest.osm.pbf` - 関東地方のOSMデータ
- `osrm_optimized.bat` - 最適化されたOSRM処理バッチファイル

## 🔧 使用方法

### 最適化処理実行

```bash
osrm_optimized.bat
```

**実行内容:**
- データ抽出（osrm-extract）
- パーティション分割（osrm-partition）
- カスタマイズ（osrm-customize）
- サーバー起動の選択

**処理の流れ:**
1. 開始時刻の表示
2. 各段階の処理実行
3. エラーチェック
4. 完了時刻の表示
5. サーバー起動の選択

## ⚡ 設定仕様

| 項目 | 設定値 |
|------|--------|
| メモリ制限 | 24GB |
| スレッド数 | 4 |
| アルゴリズム | MLD（Multi-Level Dijkstra） |

## 🔧 カスタマイズ

### 設定値の変更

`osrm_optimized.bat` の以下の行を編集：

```batch
docker run -t -v "D:\21EH_shimizu\graduate-study:/data" --memory=24g osrm/osrm-backend osrm-extract -p /opt/car.lua --threads 4 /data/kanto-latest.osm.pbf
```

### 注意事項

- メモリ制限は利用可能メモリの80%以下にしてください
- SSD使用時は特に効果的です
- 初回実行時は時間がかかりますが、2回目以降は高速化されます

## 📁 生成されるファイル

処理完了後、以下のファイルが生成されます：

- `kanto-latest.osrm` - メインデータファイル
- `kanto-latest.osrm.cell_metrics` - セルメトリクス
- `kanto-latest.osrm.cells` - セルデータ
- `kanto-latest.osrm.cnbg` - コンパクトノード
- `kanto-latest.osrm.cnbg_to_ebg` - ノードマッピング
- `kanto-latest.osrm.datasource_names` - データソース名
- `kanto-latest.osrm.ebg` - エッジベースグラフ
- `kanto-latest.osrm.ebg_nodes` - エッジベースノード
- `kanto-latest.osrm.edges` - エッジデータ
- `kanto-latest.osrm.enw` - エッジノードウェイ
- `kanto-latest.osrm.fileIndex` - ファイルインデックス
- `kanto-latest.osrm.geometry` - ジオメトリデータ
- `kanto-latest.osrm.icd` - インデックス
- `kanto-latest.osrm.maneuver_overrides` - マニューバオーバーライド
- `kanto-latest.osrm.mldgr` - MLDグラフ
- `kanto-latest.osrm.names` - 名前データ
- `kanto-latest.osrm.nbg_nodes` - ノードベースグラフノード
- `kanto-latest.osrm.partition` - パーティション
- `kanto-latest.osrm.properties` - プロパティ
- `kanto-latest.osrm.ramIndex` - RAMインデックス
- `kanto-latest.osrm.restrictions` - 制限データ
- `kanto-latest.osrm.timestamp` - タイムスタンプ
- `kanto-latest.osrm.tld` - トップレベル
- `kanto-latest.osrm.tls` - トップレベルセット
- `kanto-latest.osrm.turn_duration_penalties` - ターン時間ペナルティ
- `kanto-latest.osrm.turn_penalties_index` - ターンペナルティインデックス
- `kanto-latest.osrm.turn_weight_penalties` - ターン重みペナルティ

## 🌐 サーバー起動

処理完了後、以下のコマンドでサーバーを起動できます：

```bash
docker run -t -i -p 5000:5000 -v "D:\21EH_shimizu\graduate-study:/data" --memory=8g osrm/osrm-backend osrm-routed --algorithm mld --threads 4 /data/kanto-latest.osrm
```

**アクセス方法:**
- URL: `http://localhost:5000`

## 🐛 トラブルシューティング

### よくある問題

1. **メモリ不足エラー**
   - 他のアプリケーションを終了してください
   - システムの利用可能メモリを確認してください

2. **Dockerエラー**
   - Docker Desktopが起動していることを確認してください
   - ディスク容量が十分あることを確認してください

### ログの確認

エラーが発生した場合は、以下のログを確認してください：
- Docker ログ
- システムイベントログ
- ディスク容量

## 📞 サポート

問題が発生した場合は、以下を確認してください：
1. システム要件の確認
2. Docker環境の確認
3. ディスク容量の確認
4. メモリ使用量の確認
