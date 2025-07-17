# マルチステージビルドを使用してイメージサイズを小さくする
FROM ubuntu:22.04 as builder

# タイムゾーンの設定（インタラクティブプロンプトを避ける）
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

# 必要なパッケージをインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    curl \
    pkg-config \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 作業ディレクトリを設定
WORKDIR /app

# ソースコードをコピー
COPY CMakeLists.txt .
COPY main.cpp .

# ビルドディレクトリを作成
RUN mkdir build

# CMakeを実行してビルド
WORKDIR /app/build
RUN cmake .. -DCMAKE_BUILD_TYPE=Release
RUN make -j$(nproc)

# ランタイムイメージ（最小限）
FROM ubuntu:22.04 as runtime

# タイムゾーンの設定
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Asia/Tokyo

# ランタイムに必要な最小限のパッケージをインストール
RUN apt-get update && apt-get install -y \
    libstdc++6 \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

# 実行用ユーザーを作成（セキュリティのため）
RUN useradd -m -s /bin/bash appuser

# 作業ディレクトリを設定
WORKDIR /app

# ビルドしたバイナリをコピー
COPY --from=builder /app/build/aggregation_server .

# 実行権限を付与
RUN chmod +x aggregation_server

# ファイルの所有者を変更
RUN chown appuser:appuser aggregation_server

# 非rootユーザーに切り替え
USER appuser

# ポート8080を公開
EXPOSE 8080

# ヘルスチェック設定
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# サーバーを起動
CMD ["./aggregation_server"]