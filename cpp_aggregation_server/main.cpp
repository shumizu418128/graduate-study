#include <httplib.h>
#include <nlohmann/json.hpp>
#include <vector>
#include <unordered_map>
#include <unordered_set>
#include <cmath>
#include <algorithm>
#include <iostream>
#include <chrono>
#include <thread>
#include <mutex>
#include <future>
#include <memory>
#include <atomic>

using json = nlohmann::json;
using namespace std;

// ポイント構造体
struct Point {
    double lon;
    double lat;
    int oid;

    Point() : lon(0), lat(0), oid(0) {}
    Point(double longitude, double latitude, int object_id)
        : lon(longitude), lat(latitude), oid(object_id) {}
};

// 2D座標構造体（デカルト座標用）
struct Point2D {
    double x;
    double y;
    int oid;
    int original_index; // 元のインデックスを保持

    Point2D() : x(0), y(0), oid(0), original_index(-1) {}
    Point2D(double x_coord, double y_coord, int object_id, int idx = -1)
        : x(x_coord), y(y_coord), oid(object_id), original_index(idx) {}
};

// 高性能グリッドハッシュ用の構造体
struct GridKey {
    int grid_x;
    int grid_y;

    GridKey() : grid_x(0), grid_y(0) {}
    GridKey(int x, int y) : grid_x(x), grid_y(y) {}

    bool operator==(const GridKey& other) const {
        return grid_x == other.grid_x && grid_y == other.grid_y;
    }

    bool operator<(const GridKey& other) const {
        if (grid_x != other.grid_x) return grid_x < other.grid_x;
        return grid_y < other.grid_y;
    }
};

// GridKeyの高速ハッシュ関数
struct GridKeyHash {
    size_t operator()(const GridKey& key) const {
        // より効率的なハッシュ関数
        return ((size_t)key.grid_x << 32) | ((size_t)key.grid_y & 0xFFFFFFFF);
    }
};



/**
 * 地理座標をデカルト座標に変換
 */
vector<Point2D> convertToCartesian(const vector<Point>& points) {
    if (points.empty()) return {};

    // 参照点（重心）を計算
    double ref_lon = 0, ref_lat = 0;
    for (const auto& p : points) {
        ref_lon += p.lon;
        ref_lat += p.lat;
    }
    ref_lon /= points.size();
    ref_lat /= points.size();

    const double R = 6371000.0; // 地球半径（メートル）
    const double ref_lat_rad = ref_lat * M_PI / 180.0;

    vector<Point2D> cartesian_points;
    cartesian_points.reserve(points.size());

    for (int i = 0; i < points.size(); i++) {
        const auto& p = points[i];
        double x = R * (p.lon - ref_lon) * M_PI / 180.0 * cos(ref_lat_rad);
        double y = R * (p.lat - ref_lat) * M_PI / 180.0;
        cartesian_points.emplace_back(x, y, p.oid, i);
    }

    return cartesian_points;
}

/**
 * 凸包を計算（Graham scan アルゴリズム）
 */
vector<Point2D> computeConvexHull(vector<Point2D> points) {
    if (points.size() < 3) return points;

    // 最下部の点を見つける（y座標が最小、同じならx座標が最小）
    int min_idx = 0;
    for (int i = 1; i < points.size(); i++) {
        if (points[i].y < points[min_idx].y ||
            (points[i].y == points[min_idx].y && points[i].x < points[min_idx].x)) {
            min_idx = i;
        }
    }
    swap(points[0], points[min_idx]);

    Point2D pivot = points[0];

    // 角度でソート
    sort(points.begin() + 1, points.end(), [&pivot](const Point2D& a, const Point2D& b) {
        double cross = (a.x - pivot.x) * (b.y - pivot.y) - (a.y - pivot.y) * (b.x - pivot.x);
        if (abs(cross) < 1e-9) {
            // 共線の場合、距離で比較
            double dist_a = (a.x - pivot.x) * (a.x - pivot.x) + (a.y - pivot.y) * (a.y - pivot.y);
            double dist_b = (b.x - pivot.x) * (b.x - pivot.x) + (b.y - pivot.y) * (b.y - pivot.y);
            return dist_a < dist_b;
        }
        return cross > 0;
    });

    // Graham scan
    vector<Point2D> hull;
    for (const auto& point : points) {
        while (hull.size() >= 2) {
            Point2D& p1 = hull[hull.size() - 2];
            Point2D& p2 = hull[hull.size() - 1];
            double cross = (p2.x - p1.x) * (point.y - p1.y) - (p2.y - p1.y) * (point.x - p1.x);
            if (cross <= 0) {
                hull.pop_back();
            } else {
                break;
            }
        }
        hull.push_back(point);
    }

    return hull;
}

/**
 * 凸包の重心を計算
 */
Point2D computeCentroid(const vector<Point2D>& hull_points) {
    if (hull_points.empty()) return Point2D();

    double sum_x = 0, sum_y = 0;
    for (const auto& p : hull_points) {
        sum_x += p.x;
        sum_y += p.y;
    }

    return Point2D(sum_x / hull_points.size(), sum_y / hull_points.size(), 0);
}

/**
 * デカルト座標を地理座標に逆変換
 */
Point convertToGeographic(const Point2D& cartesian_point, double ref_lon, double ref_lat) {
    const double R = 6371000.0;
    const double ref_lat_rad = ref_lat * M_PI / 180.0;

    double lon = ref_lon + (cartesian_point.x / (R * cos(ref_lat_rad))) * 180.0 / M_PI;
    double lat = ref_lat + (cartesian_point.y / R) * 180.0 / M_PI;

    return Point(lon, lat, cartesian_point.oid);
}

/**
 * 2点間の距離の平方を計算（高速化のためsqrtを回避）
 */
double calculateDistanceSquared(const Point2D& p1, const Point2D& p2) {
    double dx = p1.x - p2.x;
    double dy = p1.y - p2.y;
    return dx * dx + dy * dy;
}

/**
 * 2点間のユークリッド距離を計算
 */
double calculateDistance(const Point2D& p1, const Point2D& p2) {
    return sqrt(calculateDistanceSquared(p1, p2));
}

/**
 * 高速空間インデックス（グリッドベース）
 */
class SpatialIndex {
private:
    unordered_map<GridKey, vector<int>, GridKeyHash> grid_map;
    double grid_size;

public:
    SpatialIndex(double cell_size) : grid_size(cell_size) {}

    void insert(const Point2D& point, int index) {
        GridKey key(
            static_cast<int>(floor(point.x / grid_size)),
            static_cast<int>(floor(point.y / grid_size))
        );
        grid_map[key].push_back(index);
    }

    // 指定範囲内の候補点を高速取得
    vector<int> getCandidates(const Point2D& center, double radius) const {
        vector<int> candidates;

        int grid_radius = static_cast<int>(ceil(radius / grid_size)) + 1;
        GridKey center_key(
            static_cast<int>(floor(center.x / grid_size)),
            static_cast<int>(floor(center.y / grid_size))
        );

        for (int dx = -grid_radius; dx <= grid_radius; dx++) {
            for (int dy = -grid_radius; dy <= grid_radius; dy++) {
                GridKey key(center_key.grid_x + dx, center_key.grid_y + dy);
                auto it = grid_map.find(key);
                if (it != grid_map.end()) {
                    candidates.insert(candidates.end(), it->second.begin(), it->second.end());
                }
            }
        }

        return candidates;
    }

    size_t getGridCount() const { return grid_map.size(); }
};

/**
 * 並列処理対応Union-Find
 */
class ThreadSafeUnionFind {
private:
    vector<atomic<int>> parent;
    vector<atomic<int>> rank;
    mutable vector<mutex> mutexes;

public:
    ThreadSafeUnionFind(int n) : parent(n), rank(n), mutexes(n) {
        for (int i = 0; i < n; i++) {
            parent[i].store(i);
            rank[i].store(0);
        }
    }

    int find(int x) {
        while (true) {
            int p = parent[x].load();
            if (p == x) return x;

            // パス圧縮
            int gp = parent[p].load();
            if (gp == p) return p;

            parent[x].compare_exchange_weak(p, gp);
            x = p;
        }
    }

    bool unite(int x, int y) {
        while (true) {
            int px = find(x);
            int py = find(y);
            if (px == py) return false;

            if (px > py) swap(px, py);

            lock_guard<mutex> lock1(mutexes[px]);
            lock_guard<mutex> lock2(mutexes[py]);

            if (find(x) != px || find(y) != py) continue;

            int rank_px = rank[px].load();
            int rank_py = rank[py].load();

            if (rank_px < rank_py) {
                parent[px].store(py);
            } else if (rank_px > rank_py) {
                parent[py].store(px);
            } else {
                parent[py].store(px);
                rank[px].store(rank_px + 1);
            }
            return true;
        }
    }
};

/**
 * 高速並列ポイント集約処理
 */
json aggregatePoints(const vector<Point>& input_points, double radius_meters) {
    auto start_time = chrono::high_resolution_clock::now();

    cout << "集約対象ポイント数: " << input_points.size() << endl;

    if (input_points.empty()) {
        return json::object();
    }

    // 参照点（重心）を計算
    double ref_lon = 0, ref_lat = 0;
    for (const auto& p : input_points) {
        ref_lon += p.lon;
        ref_lat += p.lat;
    }
    ref_lon /= input_points.size();
    ref_lat /= input_points.size();

    // デカルト座標に変換
    vector<Point2D> cartesian_points = convertToCartesian(input_points);

    cout << "高速クラスタリング開始（半径: " << radius_meters << "m）" << endl;

    // 空間インデックスを構築（グリッドサイズは半径と同じで最適化）
    double grid_size = radius_meters;
    SpatialIndex spatial_index(grid_size);

    for (int i = 0; i < cartesian_points.size(); i++) {
        spatial_index.insert(cartesian_points[i], i);
    }

    cout << "空間インデックス構築完了: " << spatial_index.getGridCount() << " グリッド" << endl;

    // 高速グループ化処理
    json result = json::object();
    int group_id = 1;
    vector<bool> processed(cartesian_points.size(), false);

    // 進捗表示用
    const int bar_width = 50;
    int last_progress = -1;
    int processed_count = 0;

    cout << "グループ化処理開始..." << endl;

    for (int i = 0; i < cartesian_points.size(); i++) {
        // 既に他のグループで処理済みの点はスキップ
        if (processed[i]) continue;

        // 進捗バー表示（処理済み点数ベース）
        int progress = static_cast<int>(100.0 * processed_count / cartesian_points.size());
        if (progress != last_progress && (progress % 5 == 0)) {
            int pos = bar_width * progress / 100;
            cout << "\r[";
            for (int j = 0; j < bar_width; ++j) {
                if (j < pos) cout << "=";
                else if (j == pos) cout << ">";
                else cout << " ";
            }
            cout << "] " << progress << "% (" << processed_count << "/" << cartesian_points.size() << ")";
            cout.flush();
            last_progress = progress;
        }

                // 候補点取得を高速化（既に処理済みの点は除外）
        vector<int> candidates = spatial_index.getCandidates(cartesian_points[i], radius_meters);
        vector<Point2D> group_points;
        vector<int> group_indices;

        // メモリ予約でパフォーマンス向上
        group_points.reserve(candidates.size());
        group_indices.reserve(candidates.size());

        // 平方距離で比較して高速化
        double radius_squared = radius_meters * radius_meters;

        for (int j : candidates) {
            if (processed[j]) continue;  // 既に処理済みの点は除外

            double distance_squared = calculateDistanceSquared(cartesian_points[i], cartesian_points[j]);
            if (distance_squared <= radius_squared) {
                group_points.push_back(cartesian_points[j]);
                group_indices.push_back(j);
            }
        }

        if (group_points.empty()) {
            processed[i] = true;
            processed_count++;
            continue;
        }

        // グループ内の全ての点を処理済みとしてマーク
        for (int idx : group_indices) {
            processed[idx] = true;
            processed_count++;
        }

        // 重心計算
        Point2D centroid;
        if (group_points.size() >= 3) {
            vector<Point2D> hull = computeConvexHull(group_points);
            if (!hull.empty()) {
                centroid = computeCentroid(hull);
            } else {
                centroid = computeCentroid(group_points);
            }
        } else {
            centroid = computeCentroid(group_points);
        }

        Point geographic_centroid = convertToGeographic(centroid, ref_lon, ref_lat);

        // 結果を格納
        result[to_string(group_id)] = {
            {"oid", group_id},
            {"lon", geographic_centroid.lon},
            {"lat", geographic_centroid.lat}
        };
        group_id++;
    }

    // 100%表示
    cout << "\r[";
    for (int j = 0; j < bar_width; ++j) cout << "=";
    cout << "] 100% (" << cartesian_points.size() << "/" << cartesian_points.size() << ")" << endl;

    auto end_time = chrono::high_resolution_clock::now();
    auto duration = chrono::duration_cast<chrono::milliseconds>(end_time - start_time);

    return result;
}

int main() {
    httplib::Server server;

    // CORS設定
    server.set_pre_routing_handler([](const httplib::Request& req, httplib::Response& res) {
        res.set_header("Access-Control-Allow-Origin", "*");
        res.set_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
        res.set_header("Access-Control-Allow-Headers", "Content-Type");
        return httplib::Server::HandlerResponse::Unhandled;
    });

    // OPTIONSリクエストの処理
    server.Options(R"(/.*)", [](const httplib::Request&, httplib::Response& res) {
        return;
    });

    // ヘルスチェックエンドポイント
    server.Get("/health", [](const httplib::Request&, httplib::Response& res) {
        res.set_content("{\"status\": \"ok\"}", "application/json");
    });

    // ポイント集約エンドポイント
    server.Post("/aggregate", [](const httplib::Request& req, httplib::Response& res) {
        try {
            // JSONデータを解析
            json request_data = json::parse(req.body);

            vector<Point> points;
            double radius = request_data.at("radius"); // 半径（メートル）ない場合は例外を投げる

            // ポイントデータを抽出
            if (request_data.contains("points")) {
                for (const auto& point_data : request_data["points"]) {
                    int oid = point_data.value("oid", 0);
                    double lon = point_data.value("lon", 0.0);
                    double lat = point_data.value("lat", 0.0);
                    points.emplace_back(lon, lat, oid);
                }
            } else {
                throw runtime_error("ポイントデータが存在しません");
            }

            // 集約処理を実行
            json result = aggregatePoints(points, radius);

            // レスポンスを作成
            json response = {
                {"status", "success"},
                {"aggregated_points", result},
                {"input_count", points.size()},
                {"output_count", result.size()}
            };

            res.set_content(response.dump(), "application/json");

        } catch (const nlohmann::json::exception& e) {
            cerr << "[aggregate endpoint][JSON例外] " << e.what() << endl;
            cerr << "  リクエストボディ: " << req.body << endl;
            json error_response = {
                {"status", "error"},
                {"type", "json_exception"},
                {"message", e.what()},
                {"request_body", req.body}
            };
            res.status = 400;
            res.set_content(error_response.dump(), "application/json");
        } catch (const std::exception& e) {
            cerr << "[aggregate endpoint][std::exception] " << e.what() << endl;
            cerr << "  リクエストボディ: " << req.body << endl;
            json error_response = {
                {"status", "error"},
                {"type", "std_exception"},
                {"message", e.what()},
                {"request_body", req.body}
            };
            res.status = 400;
            res.set_content(error_response.dump(), "application/json");
        } catch (...) {
            cerr << "[aggregate endpoint][unknown exception]" << endl;
            cerr << "  リクエストボディ: " << req.body << endl;
            json error_response = {
                {"status", "error"},
                {"type", "unknown_exception"},
                {"message", "unknown error"},
                {"request_body", req.body}
            };
            res.status = 400;
            res.set_content(error_response.dump(), "application/json");
        }
    });

    // サーバーを開始
    cout << "ポイント集約サーバーを開始しました" << endl;
    server.listen("0.0.0.0", 8080);

    cout << "サーバーが停止しました" << endl;
    return 0;
}