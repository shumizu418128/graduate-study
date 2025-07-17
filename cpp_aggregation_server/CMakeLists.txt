cmake_minimum_required(VERSION 3.16)
project(PointAggregationServer)

# C++17標準を設定
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# リリースビルド設定（最適化を有効にする）
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# コンパイラフラグ
set(CMAKE_CXX_FLAGS_RELEASE "-O3 -DNDEBUG")

# 必要なパッケージを検索
find_package(Threads REQUIRED)

# ライブラリの設定
include(FetchContent)

# httplib（HTTPサーバーライブラリ）
FetchContent_Declare(
    httplib
    GIT_REPOSITORY https://github.com/yhirose/cpp-httplib.git
    GIT_TAG v0.14.1
)

# nlohmann/json（JSONライブラリ）
FetchContent_Declare(
    nlohmann_json
    GIT_REPOSITORY https://github.com/nlohmann/json.git
    GIT_TAG v3.11.2
)

FetchContent_MakeAvailable(httplib nlohmann_json)

# 実行ファイルの作成
add_executable(aggregation_server main.cpp)

# ライブラリをリンク
target_link_libraries(aggregation_server
    PRIVATE
    Threads::Threads
    nlohmann_json::nlohmann_json
)

# httplibはヘッダーオンリーライブラリなので、インクルードディレクトリを追加
target_include_directories(aggregation_server
    PRIVATE
    ${httplib_SOURCE_DIR}
)

# Linuxの場合に必要な追加のリンクライブラリ
if(UNIX AND NOT APPLE)
    target_link_libraries(aggregation_server PRIVATE pthread)
endif()

# 最適化フラグを追加
target_compile_options(aggregation_server PRIVATE
    $<$<CONFIG:Release>:-O3 -march=native -DNDEBUG>
    $<$<CONFIG:Debug>:-g -O0>
)

# コンパイル時の警告設定
target_compile_options(aggregation_server PRIVATE
    -Wall -Wextra -Wpedantic
)

# インストール設定
install(TARGETS aggregation_server
    RUNTIME DESTINATION bin
)