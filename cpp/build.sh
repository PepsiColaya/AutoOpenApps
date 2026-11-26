#!/usr/bin/env bash
# AutoOpenApps C++ 版编译脚本（使用便携 w64devkit / MinGW-w64 g++）
set -e
W64="/c/Users/cola/WorkBuddy AI/myComputer/tools/w64devkit/bin"
cd "$(dirname "$0")"

echo "[1/2] windres ..."
"$W64/windres.exe" -c 65001 app.rc -O coff -o app.res

echo "[2/2] g++ ..."
"$W64/g++.exe" -std=c++17 -O2 -municode -mwindows -DUNICODE -D_UNICODE \
    -static -static-libgcc -static-libstdc++ -s \
    main.cpp app.res -o AutoOpenApps.exe \
    -lole32 -loleaut32 -luuid -lcomctl32 -lcomdlg32 \
    -lshell32 -ladvapi32 -lgdi32 -lshlwapi

ls -la AutoOpenApps.exe
echo "OK"
