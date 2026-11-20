#!/usr/bin/env bash
# AutoOpenApps C++ 版编译脚本
# 依赖：MinGW-w64 工具链（g++、windres 需在 PATH 中）
set -e
cd "$(dirname "$0")"

echo "[1/2] windres ..."
windres -c 65001 app.rc -O coff -o app.res

echo "[2/2] g++ ..."
g++ -std=c++17 -O2 -municode -mwindows -DUNICODE -D_UNICODE \
    -static -static-libgcc -static-libstdc++ -s \
    main.cpp app.res -o AutoOpenApps.exe \
    -lole32 -loleaut32 -luuid -lcomctl32 -lcomdlg32 \
    -lshell32 -ladvapi32 -lgdi32 -lshlwapi

ls -la AutoOpenApps.exe
echo "Build OK"
