REM Description: OSRM処理最適化バッチ
REM Shift-jisで保存し、実行すること（powershellでUTF-8のまま実行すると文字化けする）

@echo off
chcp 65001 >nul
REM OSRM処理最適化バッチ
echo OSRM処理最適化ツール - 起動
echo 開始時刻: %date% %time%
echo.

REM 固定設定（README準拠）
set THREADS=4
set MEMORY=24

REM 地域名を指定（kanto または kansai など）
set AREA=kansai

REM ファイル名を変数化
set OSM_PBF=%AREA%-latest.osm.pbf
set OSRM_FILE=%AREA%-latest.osrm
set DATA_DIR=D:\21EH_shimizu\graduate-study\OSRM\data

REM ======================================
REM リージョン設定デバッグ表示
REM ======================================
echo.
echo [デバッグ情報] リージョン設定
echo ======================================
echo リージョン: %AREA%
echo OSM_PBF: %OSM_PBF%
echo OSRM_FILE: %OSRM_FILE%
echo データディレクトリ: %DATA_DIR%
echo スレッド数: %THREADS%
echo メモリ制限: %MEMORY%GB
echo ======================================
echo.

REM ======================================
REM ファイル存在確認
REM ======================================
echo [ファイル確認]
if exist "%DATA_DIR%\%OSM_PBF%" (
    echo ? %OSM_PBF% が見つかりました
    for %%A in ("%DATA_DIR%\%OSM_PBF%") do (
        echo   サイズ: %%~zA バイト
    )
) else (
    echo ? エラー: %OSM_PBF% が見つかりません
    echo   パス: %DATA_DIR%\%OSM_PBF%
    echo.
    echo 利用可能なOSMファイル:
    dir "%DATA_DIR%\*.pbf" 2>nul || echo   (OSMファイルがありません)
    pause
    exit /b 1
)

if exist "%DATA_DIR%\%OSRM_FILE%" (
    echo ? %OSRM_FILE% が見つかりました
) else (
    echo ? %OSRM_FILE% がまだ生成されていません (初回実行時は正常です)
)

if exist "%DATA_DIR%" (
    echo ? データディレクトリが存在します
) else (
    echo ? エラー: データディレクトリが見つかりません
    echo   パス: %DATA_DIR%
    pause
    exit /b 1
)
echo.

echo.
echo 実行する処理を選択してください
echo 1. 全処理実行（データ抽出 + パーティション分割 + カスタマイズ）
echo 2. サーバーのみ起動（既存データ使用）
set /p process_choice="番号を入力してください (1/2): "


if "%process_choice%"=="1" (
    echo.
    echo =====================================
    echo 1. データ抽出 開始...
    echo =====================================
    echo リージョン: %AREA%
    echo 入力ファイル: /data/%OSM_PBF%
    echo 出力ファイル: /data/%OSRM_FILE%
    echo スレッド数: %THREADS%
    echo メモリ制限: %MEMORY%GB
    echo.
    docker run -t -v "%DATA_DIR%:/data" --memory=%MEMORY%g osrm/osrm-backend osrm-extract -p /opt/foot.lua --threads %THREADS% /data/%OSM_PBF%
    if %errorlevel% neq 0 (
        echo.
        echo [エラー] データ抽出に失敗しました
        echo リージョン設定を確認してください: %AREA%
        echo OSMファイルが存在するか確認: %DATA_DIR%\%OSM_PBF%
        pause
        exit /b 1
    )

    echo.
    echo =====================================
    echo 2. パーティション分割 開始...
    echo =====================================
    echo リージョン: %AREA%
    echo 対象ファイル: /data/%OSRM_FILE%
    echo スレッド数: %THREADS%
    echo.
    docker run -t -v "%DATA_DIR%:/data" --memory=%MEMORY%g osrm/osrm-backend osrm-partition --threads %THREADS% /data/%OSRM_FILE%
    if %errorlevel% neq 0 (
        echo.
        echo [エラー] パーティション分割に失敗しました
        echo リージョン設定を確認してください: %AREA%
        echo 抽出済みファイルが存在するか確認: %DATA_DIR%\%OSRM_FILE%
        pause
        exit /b 1
    )

    echo.
    echo =====================================
    echo 3. カスタマイズ 開始...
    echo =====================================
    echo リージョン: %AREA%
    echo 対象ファイル: /data/%OSRM_FILE%
    echo スレッド数: %THREADS%
    echo.
    docker run -t -v "%DATA_DIR%:/data" --memory=%MEMORY%g osrm/osrm-backend osrm-customize --threads %THREADS% /data/%OSRM_FILE%
    if %errorlevel% neq 0 (
        echo.
        echo [エラー] カスタマイズに失敗しました
        echo リージョン設定を確認してください: %AREA%
        echo パーティション分割済みファイルが存在するか確認: %DATA_DIR%\%OSRM_FILE%
        pause
        exit /b 1
    )

    echo.
    echo データ処理が完了しました。
) else (
    echo.
    echo 既存データを使ってサーバーのみ起動します...
    echo リージョン: %AREA%
    echo.
)

echo.
echo 終了時刻: %date% %time%

echo.
echo サーバーを起動しますか？ (y/n)
set /p choice=

if /i "%choice%"=="y" (
    echo.
    echo =====================================
    echo サーバーを起動します...
    echo =====================================
    echo リージョン: %AREA%
    echo データファイル: /data/%OSRM_FILE%
    echo ポート: 5000
    echo アルゴリズム: mld
    echo スレッド数: %THREADS%
    echo メモリ制限: 8GB
    echo.
    echo ? サーバーが起動しました
    echo   アクセスURL: http://localhost:5000
    echo   リージョン確認済み: %AREA%
    echo.
    docker run -t -i -p 5000:5000 -v "%DATA_DIR%:/data" --memory=8g osrm/osrm-backend osrm-routed --algorithm mld --threads %THREADS% /data/%OSRM_FILE%
) else (
    echo サーバーの起動をキャンセルしました
)

pause
