REM Description: OSRM処理最適化バッチ
REM Shift-jisで保存し、実行すること（powershellでUTF-8のまま実行すると文字化けする）

@echo off
REM OSRM処理最適化バッチ
echo OSRM処理最適化ツール - 起動
echo 開始時刻: %date% %time%


REM 固定設定（README準拠）
set THREADS=4
set MEMORY=24

REM 地域名を指定（kanto または kansai など）
set AREA=kanto

REM ファイル名を変数化
set OSM_PBF=%AREA%-latest.osm.pbf
set OSRM_FILE=%AREA%-latest.osrm

echo スレッド数: %THREADS%
echo メモリ制限: %MEMORY%GB

echo.
echo 実行する処理を選択してください
echo 1. 全処理実行（データ抽出 + パーティション分割 + カスタマイズ）
echo 2. サーバーのみ起動（既存データ使用）
set /p process_choice="番号を入力してください (1/2): "


if "%process_choice%"=="1" (
    echo.
    echo 1. データ抽出 開始...
    docker run -t -v "D:\21EH_shimizu\graduate-study\OSRM\data:/data" --memory=%MEMORY%g osrm/osrm-backend osrm-extract -p /opt/foot.lua --threads %THREADS% /data/%OSM_PBF%
    if %errorlevel% neq 0 (
        echo エラー: データ抽出に失敗しました
        pause
        exit /b 1
    )

    echo.
    echo 2. パーティション分割 開始...
    docker run -t -v "D:\21EH_shimizu\graduate-study\OSRM\data:/data" --memory=%MEMORY%g osrm/osrm-backend osrm-partition --threads %THREADS% /data/%OSRM_FILE%
    if %errorlevel% neq 0 (
        echo エラー: パーティション分割に失敗しました
        pause
        exit /b 1
    )

    echo.
    echo 3. カスタマイズ 開始...
    docker run -t -v "D:\21EH_shimizu\graduate-study\OSRM\data:/data" --memory=%MEMORY%g osrm/osrm-backend osrm-customize --threads %THREADS% /data/%OSRM_FILE%
    if %errorlevel% neq 0 (
        echo エラー: カスタマイズに失敗しました
        pause
        exit /b 1
    )

    echo.
    echo データ処理が完了しました。
) else (
    echo.
    echo 既存データを使ってサーバーのみ起動します...
)

echo.
echo 終了時刻: %date% %time%

echo.
echo サーバーを起動しますか？ (y/n)
set /p choice=

if /i "%choice%"=="y" (
    echo サーバーを起動します...
    docker run -t -i -p 5000:5000 -v "D:\21EH_shimizu\graduate-study\OSRM\data:/data" --memory=8g osrm/osrm-backend osrm-routed --algorithm mld --threads %THREADS% /data/%OSRM_FILE%
)

pause
