REM Description: OSRM�����œK���o�b�`
REM Shift-jis�ŕۑ����A���s���邱�Ɓipowershell��UTF-8�̂܂܎��s����ƕ�����������j

@echo off
REM OSRM�����œK���o�b�`
echo OSRM�����œK���c�[�� - �N��
echo �J�n����: %date% %time%

REM �Œ�ݒ�iREADME�����j
set THREADS=4
set MEMORY=24

echo �X���b�h��: %THREADS%
echo ����������: %MEMORY%GB

echo.
echo ���s���鏈����I�����Ă�������
echo 1. �S�������s�i�f�[�^���o + �p�[�e�B�V�������� + �J�X�^�}�C�Y�j
echo 2. �T�[�o�[�̂݋N���i�����f�[�^�g�p�j
set /p process_choice="�ԍ�����͂��Ă������� (1/2): "

if "%process_choice%"=="1" (
    echo.
    echo 1. �f�[�^���o �J�n...
    docker run -t -v "D:\21EH_shimizu\graduate-study:/data" --memory=24g osrm/osrm-backend osrm-extract -p /opt/foot.lua --threads 4 /data/kanto-latest.osm.pbf
    if %errorlevel% neq 0 (
        echo �G���[: �f�[�^���o�Ɏ��s���܂���
        pause
        exit /b 1
    )

    echo.
    echo 2. �p�[�e�B�V�������� �J�n...
    docker run -t -v "D:\21EH_shimizu\graduate-study:/data" --memory=24g osrm/osrm-backend osrm-partition --threads 4 /data/kanto-latest.osrm
    if %errorlevel% neq 0 (
        echo �G���[: �p�[�e�B�V���������Ɏ��s���܂���
        pause
        exit /b 1
    )

    echo.
    echo 3. �J�X�^�}�C�Y �J�n...
    docker run -t -v "D:\21EH_shimizu\graduate-study:/data" --memory=24g osrm/osrm-backend osrm-customize --threads 4 /data/kanto-latest.osrm
    if %errorlevel% neq 0 (
        echo �G���[: �J�X�^�}�C�Y�Ɏ��s���܂���
        pause
        exit /b 1
    )

    echo.
    echo �f�[�^�������������܂����B
) else (
    echo.
    echo �����f�[�^���g���ăT�[�o�[�̂݋N�����܂�...
)

echo.
echo �I������: %date% %time%

echo.
echo �T�[�o�[���N�����܂����H (y/n)
set /p choice=
if /i "%choice%"=="y" (
    echo �T�[�o�[���N�����܂�...
    docker run -t -i -p 5000:5000 -v "D:\21EH_shimizu\graduate-study:/data" --memory=8g osrm/osrm-backend osrm-routed --algorithm mld --threads %THREADS% /data/kanto-latest.osrm
)

pause
