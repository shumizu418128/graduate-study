import zipfile
import os
import glob
import shutil

# フォルダパス
zip_dir = r'D:\21EH_shimizu\Download\基盤地図情報大阪'
# BldAファイルの抽出先
output_dir = os.path.join(zip_dir, 'BldA_files')
os.makedirs(output_dir, exist_ok=True)

# zip_dir配下のすべてのzipファイルを再帰的に取得
for root, dirs, files in os.walk(zip_dir):
    for file in files:
        if file.lower().endswith('.zip'):
            zip_path = os.path.join(root, file)
            extract_dir = os.path.splitext(zip_path)[0]
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_dir)
                # BldAを含むファイルだけ抽出
                for name in zip_ref.namelist():
                    if 'BldA' in name:
                        src_path = os.path.join(extract_dir, name)
                        if os.path.exists(src_path):
                            shutil.copy(src_path, output_dir)
                            print(f'Extracted: {src_path} -> {output_dir}')