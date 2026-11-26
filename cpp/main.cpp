// ============================================================
// AutoOpenApps (C++ / Win32 原生版)
// 开机后按计划自动打开常用软件（带确认弹窗与倒计时）
// 无 Python / Qt 运行时依赖，单文件 exe
// ------------------------------------------------------------
// 编译（MinGW-w64 g++）:
//   windres app.rc -O coff -o app.res
//   g++ -std=c++17 -O2 -municode -mwindows -DUNICODE -D_UNICODE
//       -static -static-libgcc -static-libstdc++ -s
//       main.cpp app.res -o AutoOpenApps.exe
//       -lole32 -loleaut32 -luuid -lcomctl32 -lcomdlg32
//       -lshell32 -ladvapi32 -lgdi32 -lshlwapi
// ============================================================
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#define _WIN32_WINNT 0x0605
#include <windows.h>
#include <commctrl.h>
#include <commdlg.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shlwapi.h>
#include <string>
#include <vector>
#include <set>
#include <fstream>
#include <sstream>
#include <algorithm>
#include <cwchar>

#ifndef EM_SETCUEBANNER
#define EM_SETCUEBANNER 0x1501
#endif

#pragma comment(lib, "comctl32.lib")

// ------------------------------------------------------------
// 基本常量
// ------------------------------------------------------------
static const wchar_t* MAIN_CLASS   = L"AutoOpenApps_MainWnd";
static const wchar_t* EDIT_CLASS   = L"AutoOpenApps_EditDlg";
static const wchar_t* INDEX_CLASS  = L"AutoOpenApps_IndexDlg";
static const wchar_t* CONFIRM_CLASS= L"AutoOpenApps_ConfirmWnd";

enum {
    IDC_LIST     = 2001,
    IDC_ADD      = 2002,
    IDC_ADDIDX   = 2003,
    IDC_EDIT     = 2004,
    IDC_DEL      = 2005,
    IDC_RUN      = 2006,
    IDC_AUTORUN  = 2007,
    IDC_STATUS   = 2008,
    IDC_TIMEOUT  = 2009, // 启动倒计时输入框
    // 编辑对话框
    IDC_E_NAME   = 3001,
    IDC_E_PATH   = 3002,
    IDC_E_BROWSE = 3003,
    IDC_E_ENABLE = 3004,
    IDC_E_DOW0   = 3010, // 3010..3016 周一..周日
    IDC_E_OK     = 3017,
    IDC_E_CANCEL = 3018,
    // 索引对话框
    IDC_I_SEARCH = 4001,
    IDC_I_REFISH = 4002,
    IDC_I_LIST   = 4003,
    IDC_I_ADD    = 4004,
    IDC_I_COUNT  = 4005,
    // 确认窗口
    IDC_C_LIST   = 5001,
    IDC_C_LABEL  = 5002,
    IDC_C_OK     = 5003,
    IDC_C_CANCEL = 5004,
};

// ------------------------------------------------------------
// 数据结构
// ------------------------------------------------------------
struct AppItem {
    std::wstring name;
    std::wstring path;
    int  days    = 0x7F;   // bit0=周一 ... bit6=周日
    bool enabled = true;
};

struct FoundApp {
    std::wstring name;
    std::wstring path;
};

static std::vector<AppItem>  g_apps;          // 用户配置的软件
static int                   g_confirmSeconds = 30; // 0 = 手动确认
static HFONT                 g_font           = NULL;
static HFONT                 g_fontBig        = NULL;
static HINSTANCE             g_hInst          = NULL;
static double                g_scale          = 1.0;

// 前置声明（定义在后文）
static std::wstring GetWndText(HWND h);
static void UpdateStatusText();

// ------------------------------------------------------------
// 字符串 / 文件工具
// ------------------------------------------------------------
static std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return L"";
    int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), NULL, 0);
    std::wstring w((size_t)n, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.data(), (int)s.size(), &w[0], n);
    return w;
}

static std::string WideToUtf8(const std::wstring& w) {
    if (w.empty()) return "";
    int n = WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), NULL, 0, NULL, NULL);
    std::string s((size_t)n, 0);
    WideCharToMultiByte(CP_UTF8, 0, w.data(), (int)w.size(), &s[0], n, NULL, NULL);
    return s;
}

static std::wstring LowerCopy(const std::wstring& s) {
    std::wstring r = s;
    if (!r.empty()) CharLowerBuffW(&r[0], (DWORD)r.size());
    return r;
}

static bool ContainsI(const std::wstring& hay, const std::wstring& needle) {
    if (needle.empty()) return true;
    return LowerCopy(hay).find(LowerCopy(needle)) != std::wstring::npos;
}

static std::wstring FileBaseName(const std::wstring& p) {
    size_t i = p.find_last_of(L"\\/");
    return (i == std::wstring::npos) ? p : p.substr(i + 1);
}

static std::wstring Trim(const std::wstring& s) {
    size_t a = s.find_first_not_of(L" \t\r\n");
    if (a == std::wstring::npos) return L"";
    size_t b = s.find_last_not_of(L" \t\r\n");
    return s.substr(a, b - a + 1);
}

static std::wstring DirOf(const std::wstring& p) {
    size_t i = p.find_last_of(L"\\/");
    return (i == std::wstring::npos) ? L"" : p.substr(0, i);
}

// ------------------------------------------------------------
// 配置目录与读写
// ------------------------------------------------------------
static std::wstring GetAppDataDir() {
    PWSTR p = NULL;
    std::wstring dir;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_RoamingAppData, 0, NULL, &p))) {
        dir = std::wstring(p) + L"\\AutoOpenApps";
        CoTaskMemFree(p);
    } else {
        wchar_t buf[MAX_PATH] = {0};
        GetEnvironmentVariableW(L"APPDATA", buf, MAX_PATH);
        dir = std::wstring(buf) + L"\\AutoOpenApps";
    }
    CreateDirectoryW(dir.c_str(), NULL);
    return dir;
}

static std::wstring AppsPath()    { return GetAppDataDir() + L"\\apps.txt"; }
static std::wstring ConfigPath()  { return GetAppDataDir() + L"\\config.txt"; }

static void SyncAutoRunLnk();   // 前置声明：有启用软件时确保自启快捷方式存在

static void LoadApps() {
    g_apps.clear();
    std::ifstream f(AppsPath().c_str(), std::ios::binary);
    if (!f.is_open()) return;
    std::string line;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        if (line.empty()) continue;
        if (!line.empty() && (unsigned char)line[0] == 0xEF &&
            line.size() > 2 && (unsigned char)line[1] == 0xBB && (unsigned char)line[2] == 0xBF)
            line = line.substr(3);
        std::vector<std::string> parts;
        std::string cur;
        for (char c : line) {
            if (c == '\t') { parts.push_back(cur); cur.clear(); }
            else cur.push_back(c);
        }
        parts.push_back(cur);
        if (parts.size() < 2) continue;
        AppItem it;
        it.name = Utf8ToWide(parts[0]);
        it.path = Utf8ToWide(parts[1]);
        it.days = 0x7F;
        it.enabled = true;
        if (parts.size() > 2) it.days = atoi(parts[2].c_str());
        if (parts.size() > 3) it.enabled = (parts[3] == "1");
        if (it.days <= 0) it.days = 0x7F;
        if (!it.path.empty()) g_apps.push_back(it);
    }
}

static void SaveApps() {
    std::ofstream f(AppsPath().c_str(), std::ios::binary | std::ios::trunc);
    if (!f.is_open()) return;
    f.write("\xEF\xBB\xBF", 3);
    for (const AppItem& it : g_apps) {
        f << WideToUtf8(it.name) << '\t' << WideToUtf8(it.path) << '\t'
          << it.days << '\t' << (it.enabled ? 1 : 0) << '\n';
    }
    SyncAutoRunLnk();
}

static void LoadConfig() {
    g_confirmSeconds = 30;
    std::ifstream f(ConfigPath().c_str(), std::ios::binary);
    if (!f.is_open()) {
        std::ofstream fo(ConfigPath().c_str(), std::ios::binary | std::ios::trunc);
        fo << "confirm_seconds=30\n";
        return;
    }
    std::string line;
    bool first = true;
    while (std::getline(f, line)) {
        if (!line.empty() && line.back() == '\r') line.pop_back();
        // 跳过 UTF-8 BOM（兼容带 BOM 的配置文件）
        if (first) {
            first = false;
            if (line.size() > 2 && (unsigned char)line[0] == 0xEF &&
                (unsigned char)line[1] == 0xBB && (unsigned char)line[2] == 0xBF)
                line = line.substr(3);
        }
        size_t eq = line.find('=');
        if (eq == std::string::npos) continue;
        std::string k = line.substr(0, eq), v = line.substr(eq + 1);
        if (k == "confirm_seconds") g_confirmSeconds = atoi(v.c_str());
    }
    if (g_confirmSeconds < 0 || g_confirmSeconds > 300) g_confirmSeconds = 30;
}

static void SaveConfig() {
    std::ofstream f(ConfigPath().c_str(), std::ios::binary | std::ios::trunc);
    if (!f.is_open()) return;
    f << "confirm_seconds=" << g_confirmSeconds << "\n";
}

// 从输入框读取倒计时并保存（0~300，非法值回退为当前值）
static void ApplyTimeoutFromEdit(HWND hwnd) {
    HWND ed = GetDlgItem(hwnd, IDC_TIMEOUT);
    if (!ed) return;
    std::wstring s = GetWndText(ed);
    int v = 0;
    bool ok = true;
    if (s.empty()) ok = false;
    for (wchar_t c : s) {
        if (c < L'0' || c > L'9') { ok = false; break; }
        v = v * 10 + (c - L'0');
        if (v > 100000) { ok = false; break; }
    }
    if (!ok || v < 0 || v > 300) {
        wchar_t buf[16];
        swprintf(buf, 16, L"%d", g_confirmSeconds);
        SetWindowTextW(ed, buf);
        return;
    }
    if (v != g_confirmSeconds) {
        g_confirmSeconds = v;
        SaveConfig();
        UpdateStatusText();
    }
}

// ------------------------------------------------------------
// 星期工具（bit0=周一 ... bit6=周日）
// ------------------------------------------------------------
static int TodayBit() {
    SYSTEMTIME st;
    GetLocalTime(&st);
    int idx = (st.wDayOfWeek == 0) ? 6 : (st.wDayOfWeek - 1);
    return 1 << idx;
}

static std::wstring DaysText(int mask) {
    if (mask <= 0 || mask >= 0x7F) return L"每天";
    if (mask == 0x1F) return L"周一至周五";
    if (mask == 0x60) return L"周六、周日";
    static const wchar_t* names[] = {L"一",L"二",L"三",L"四",L"五",L"六",L"日"};
    std::wstring s;
    for (int i = 0; i < 7; i++) {
        if (mask & (1 << i)) {
            if (!s.empty()) s += L"、";
            s += std::wstring(L"周") + names[i];
        }
    }
    return s.empty() ? L"每天" : s;
}

// ------------------------------------------------------------
// 启动软件
// ------------------------------------------------------------
static bool LaunchApp(const std::wstring& path) {
    if (path.empty()) return false;
    HINSTANCE h = ShellExecuteW(NULL, L"open", path.c_str(), NULL, NULL, SW_SHOWNORMAL);
    return ((INT_PTR)h > 32);
}

// ------------------------------------------------------------
// 本机已安装软件索引（注册表卸载表）
// ------------------------------------------------------------
static bool IsJunkExeName(const std::wstring& name) {
    std::wstring n = LowerCopy(name);
    if (n.find(L"uninst") == 0) return true;
    if (n.find(L"setup") == 0) return true;
    if (n == L"au_.exe" || n == L"kill.exe") return true;
    return false;
}

static std::wstring FindExeInDir(const std::wstring& dir) {
    if (dir.empty()) return L"";
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((dir + L"\\*.exe").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return L"";
    std::wstring best;
    do {
        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) continue;
        std::wstring fn = fd.cFileName;
        if (IsJunkExeName(fn)) continue;
        if (fn.size() >= 4 && LowerCopy(fn).find(L".exe") == fn.size() - 4) { best = fn; break; }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
    return best.empty() ? L"" : dir + L"\\" + best;
}

static std::wstring CleanIconPath(const std::wstring& s) {
    std::wstring v = Trim(s);
    if (!v.empty() && v.front() == L'"') {
        size_t e = v.find(L'"', 1);
        if (e != std::wstring::npos) v = v.substr(1, e - 1);
        else v = v.substr(1);
    } else {
        size_t c = v.find(L',');
        if (c != std::wstring::npos) v = v.substr(0, c);
    }
    return v;
}

static bool ReadRegString(HKEY key, const wchar_t* value, std::wstring& out) {
    DWORD type = 0, cb = 0;
    if (RegQueryValueExW(key, value, NULL, &type, NULL, &cb) != ERROR_SUCCESS) return false;
    if (type != REG_SZ && type != REG_EXPAND_SZ) return false;
    std::vector<wchar_t> buf(cb / sizeof(wchar_t) + 1, 0);
    if (RegQueryValueExW(key, value, NULL, &type, (LPBYTE)buf.data(), &cb) != ERROR_SUCCESS) return false;
    out.assign(buf.data());
    return true;
}

static void ScanHive(HKEY root, const wchar_t* path, std::vector<FoundApp>& out, std::set<std::wstring>& seen) {
    HKEY hk;
    if (RegOpenKeyExW(root, path, 0, KEY_READ, &hk) != ERROR_SUCCESS) return;
    DWORD subkeys = 0, maxLen = 0;
    if (RegQueryInfoKeyW(hk, NULL, NULL, NULL, &subkeys, &maxLen, NULL, NULL, NULL, NULL, NULL, NULL) != ERROR_SUCCESS) {
        RegCloseKey(hk);
        return;
    }
    std::vector<wchar_t> name(maxLen + 2, 0);
    for (DWORD i = 0; i < subkeys; i++) {
        DWORD len = maxLen + 1;
        if (RegEnumKeyExW(hk, i, name.data(), &len, NULL, NULL, NULL, NULL) != ERROR_SUCCESS) continue;
        HKEY sk;
        if (RegOpenKeyExW(hk, name.data(), 0, KEY_READ, &sk) != ERROR_SUCCESS) continue;
        std::wstring displayName, installLoc, displayIcon;
        ReadRegString(sk, L"DisplayName", displayName);
        ReadRegString(sk, L"InstallLocation", installLoc);
        ReadRegString(sk, L"DisplayIcon", displayIcon);
        RegCloseKey(sk);

        displayName = Trim(displayName);
        if (displayName.empty()) continue;

        std::wstring exe;
        std::wstring loc = Trim(installLoc);
        if (!loc.empty() && loc.back() != L'\\') loc += L"\\";
        if (!loc.empty() && PathFileExistsW(loc.c_str()))
            exe = FindExeInDir(loc);
        if (exe.empty() && !displayIcon.empty()) {
            std::wstring ic = CleanIconPath(displayIcon);
            if (!ic.empty() && PathFileExistsW(ic.c_str()))
                exe = ic;
        }
        if (exe.empty()) continue;
        if (LowerCopy(exe).find(L"autoopenapps") != std::wstring::npos) continue;

        std::wstring key = LowerCopy(exe);
        if (seen.count(key)) continue;
        seen.insert(key);
        out.push_back({displayName, exe});
    }
    RegCloseKey(hk);
}

static std::vector<FoundApp> ScanInstalledApps() {
    std::vector<FoundApp> out;
    std::set<std::wstring> seen;
    ScanHive(HKEY_LOCAL_MACHINE, L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall", out, seen);
    ScanHive(HKEY_LOCAL_MACHINE, L"SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall", out, seen);
    ScanHive(HKEY_CURRENT_USER,  L"SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall", out, seen);
    return out;
}

// ------------------------------------------------------------
// 开机自启快捷方式
// ------------------------------------------------------------
static std::wstring StartupLnkPath() {
    PWSTR p = NULL;
    std::wstring dir;
    if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_Startup, 0, NULL, &p))) {
        dir = p;
        CoTaskMemFree(p);
    } else {
        wchar_t buf[MAX_PATH] = {0};
        SHGetFolderPathW(NULL, CSIDL_STARTUP, NULL, 0, buf);
        dir = buf;
    }
    return dir + L"\\AutoOpenApps.lnk";
}

static bool IsAutoRunInstalled() {
    return PathFileExistsW(StartupLnkPath().c_str()) ? true : false;
}

static bool InstallAutoRun() {
    wchar_t exe[MAX_PATH] = {0};
    GetModuleFileNameW(NULL, exe, MAX_PATH);
    IShellLinkW* sl = NULL;
    HRESULT hr = CoCreateInstance(CLSID_ShellLink, NULL, CLSCTX_INPROC_SERVER, IID_IShellLinkW, (void**)&sl);
    if (FAILED(hr)) return false;
    sl->SetPath(exe);
    sl->SetArguments(L"--auto");
    sl->SetDescription(L"AutoOpenApps 开机启动确认");
    IPersistFile* pf = NULL;
    bool ok = false;
    if (SUCCEEDED(sl->QueryInterface(IID_IPersistFile, (void**)&pf))) {
        ok = SUCCEEDED(pf->Save(StartupLnkPath().c_str(), TRUE));
        pf->Release();
    }
    sl->Release();
    return ok;
}

static void RemoveAutoRun() {
    // 重试数次：文件可能被杀软/索引服务短暂占用
    for (int i = 0; i < 5; i++) {
        if (DeleteFileW(StartupLnkPath().c_str())) break;
        Sleep(100);
    }
}

// 根据软件清单自动维护启动文件夹快捷方式：有启用软件则存在，全部停用则移除
static void SyncAutoRunLnk() {
    bool anyEnabled = false;
    for (const AppItem& a : g_apps)
        if (a.enabled) { anyEnabled = true; break; }
    if (anyEnabled && !IsAutoRunInstalled())
        InstallAutoRun();
    else if (!anyEnabled && IsAutoRunInstalled())
        RemoveAutoRun();
}

// ------------------------------------------------------------
// 控件创建辅助
// ------------------------------------------------------------
static HWND Mk(HWND parent, const wchar_t* cls, const wchar_t* text, DWORD style,
               int x, int y, int w, int h, int id) {
    HWND ctl = CreateWindowExW(0, cls, text, WS_CHILD | WS_VISIBLE | style,
                             (int)(x * g_scale), (int)(y * g_scale),
                             (int)(w * g_scale), (int)(h * g_scale),
                             parent, (HMENU)(INT_PTR)id, g_hInst, NULL);
    if (g_font) SendMessageW(ctl, WM_SETFONT, (WPARAM)g_font, TRUE);
    return ctl;
}

static int ScaleI(int v) { return (int)(v * g_scale); }

// 读控件文本：Edit 控件必须用 WM_GETTEXT（GetWindowText 对本进程 Edit 不可靠）
static std::wstring GetWndText(HWND h) {
    if (!h) return L"";
    int n = (int)SendMessageW(h, WM_GETTEXTLENGTH, 0, 0);
    if (n <= 0) return L"";
    std::wstring s((size_t)n + 1, 0);
    SendMessageW(h, WM_GETTEXT, (WPARAM)n + 1, (LPARAM)s.data());
    s.resize((size_t)n);
    return s;
}

// ------------------------------------------------------------
// 模态循环辅助（自建对话框用）
// ------------------------------------------------------------
static void RunModalLoop(HWND dlg, HWND parent) {
    EnableWindow(parent, FALSE);
    MSG m;
    for (;;) {
        BOOL r = GetMessageW(&m, NULL, 0, 0);
        if (r <= 0) break;
        if (!IsWindow(dlg)) break;
        if (!IsDialogMessageW(dlg, &m)) {
            TranslateMessage(&m);
            DispatchMessageW(&m);
        }
    }
    if (parent && IsWindow(parent)) {
        EnableWindow(parent, TRUE);
        SetForegroundWindow(parent);
    }
}

// ------------------------------------------------------------
// 编辑对话框（新增 / 修改单个软件）
// ------------------------------------------------------------
static void ShowEditDlg(HWND parent, int index);   // index = -1 表示新增
static void ShowIndexDlg(HWND parent);

static HWND g_mainWnd = NULL;

static void UpdateStatusText() {
    if (!g_mainWnd) return;
    int enabledCount = 0;
    for (const AppItem& a : g_apps)
        if (a.enabled) enabledCount++;
    HWND st = GetDlgItem(g_mainWnd, IDC_STATUS);
    wchar_t buf[1024];
    swprintf(buf, 1024,
             L"配置: %ls    |    参与开机启动: %d 个软件    |    启动快捷方式: %ls    |    确认倒计时: %d 秒 %ls",
             AppsPath().c_str(),
             enabledCount,
             IsAutoRunInstalled() ? L"已创建" : L"未创建",
             g_confirmSeconds,
             g_confirmSeconds == 0 ? L"(手动确认)" : L"(0 表示手动确认)");
    SetWindowTextW(st, buf);
}

static void UpdateButtons() {
    HWND lv = GetDlgItem(g_mainWnd, IDC_LIST);
    int selCount = 0;
    bool allEnabled = true;
    int s = -1;
    while ((s = ListView_GetNextItem(lv, s, LVNI_SELECTED)) >= 0) {
        selCount++;
        LVITEMW vi = {0};
        vi.mask = LVIF_PARAM;
        vi.iItem = s;
        ListView_GetItem(lv, &vi);
        size_t idx = (size_t)vi.lParam;
        if (idx < g_apps.size() && !g_apps[idx].enabled) allEnabled = false;
    }
    EnableWindow(GetDlgItem(g_mainWnd, IDC_EDIT), selCount == 1);
    EnableWindow(GetDlgItem(g_mainWnd, IDC_DEL),  selCount >= 1);
    EnableWindow(GetDlgItem(g_mainWnd, IDC_RUN),  selCount >= 1);
    EnableWindow(GetDlgItem(g_mainWnd, IDC_AUTORUN), selCount >= 1);
    // 按选中项的开机启动状态动态切换按钮文字
    HWND btn = GetDlgItem(g_mainWnd, IDC_AUTORUN);
    if (selCount == 0)
        SetWindowTextW(btn, L"设置开机启动");
    else
        SetWindowTextW(btn, allEnabled ? L"移除开机启动" : L"设为开机启动");
}

static void RefreshList() {
    HWND lv = GetDlgItem(g_mainWnd, IDC_LIST);
    ListView_DeleteAllItems(lv);
    for (size_t i = 0; i < g_apps.size(); i++) {
        const AppItem& it = g_apps[i];
        wchar_t idx[16];
        swprintf(idx, 16, L"%d", (int)(i + 1));
        LVITEMW vi = {0};
        vi.mask = LVIF_TEXT | LVIF_PARAM;
        vi.iItem = (int)i;
        vi.pszText = idx;
        vi.lParam = (LPARAM)i;
        int row = ListView_InsertItem(lv, &vi);
        if (row < 0) continue;
        ListView_SetItemText(lv, row, 1, (LPWSTR)it.name.c_str());
        ListView_SetItemText(lv, row, 2, (LPWSTR)it.path.c_str());
        std::wstring plan = DaysText(it.days);
        ListView_SetItemText(lv, row, 3, (LPWSTR)plan.c_str());
        ListView_SetItemText(lv, row, 4, (LPWSTR)(it.enabled ? L"开机启动" : L"已停用"));
    }
    UpdateButtons();
    UpdateStatusText();
}

static void LayoutMain(HWND hwnd, int w, int h) {
    int pad = ScaleI(12), bh = ScaleI(32), gap = ScaleI(8);
    int y = pad;
    int x = pad;
    struct { int id; int w; } btns[] = {
        {IDC_ADD, 96}, {IDC_ADDIDX, 118}, {IDC_EDIT, 70},
        {IDC_DEL, 70}, {IDC_RUN, 96}, {IDC_AUTORUN, 132},
    };
    for (auto& b : btns) {
        MoveWindow(GetDlgItem(hwnd, b.id), x, y, ScaleI(b.w), bh, TRUE);
        x += ScaleI(b.w) + gap;
    }
    int listY = y + bh + ScaleI(10);
    int rowH = ScaleI(30);
    int rowY = h - ScaleI(28) - rowH - ScaleI(6);
    MoveWindow(GetDlgItem(hwnd, IDC_LIST), pad, listY,
               w - pad * 2, rowY - listY - ScaleI(6), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_STATUS), pad, h - ScaleI(28),
               w - pad * 2, ScaleI(22), TRUE);
    int labW = ScaleI(130);
    MoveWindow(GetDlgItem(hwnd, 9100), pad, rowY, labW, rowH, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_TIMEOUT), pad + labW, rowY, ScaleI(90), rowH, TRUE);
    MoveWindow(GetDlgItem(hwnd, 9101), pad + labW + ScaleI(100), rowY,
               w - pad * 2 - labW - ScaleI(100), rowH, TRUE);
}

static void DoDelete() {
    HWND lv = GetDlgItem(g_mainWnd, IDC_LIST);
    int sel = ListView_GetNextItem(lv, -1, LVNI_SELECTED);
    if (sel < 0) return;
    LVITEMW vi = {0};
    vi.mask = LVIF_PARAM;
    vi.iItem = sel;
    ListView_GetItem(lv, &vi);
    size_t idx = (size_t)vi.lParam;
    if (idx >= g_apps.size()) return;
    wchar_t msg[512];
    swprintf(msg, 512, L"确定删除「%ls」吗？\n（仅从列表移除，不会卸载软件本身）", g_apps[idx].name.c_str());
    if (MessageBoxW(g_mainWnd, msg, L"删除确认", MB_OKCANCEL | MB_ICONQUESTION) != IDOK) return;
    g_apps.erase(g_apps.begin() + idx);
    SaveApps();
    RefreshList();
}

static void DoRunSelected() {
    HWND lv = GetDlgItem(g_mainWnd, IDC_LIST);
    std::vector<size_t> rows;
    int s = -1;
    while ((s = ListView_GetNextItem(lv, s, LVNI_SELECTED)) >= 0) {
        LVITEMW vi = {0};
        vi.mask = LVIF_PARAM;
        vi.iItem = s;
        ListView_GetItem(lv, &vi);
        rows.push_back((size_t)vi.lParam);
    }
    if (rows.empty()) return;
    int ok = 0;
    for (size_t r : rows)
        if (LaunchApp(g_apps[r].path)) ok++;
    wchar_t msg[128];
    swprintf(msg, 128, L"已启动 %d / %d 个软件。", ok, (int)rows.size());
    MessageBoxW(g_mainWnd, msg, L"立即启动", MB_OK | MB_ICONINFORMATION);
}

// 批量设置/移除选中软件的开机启动（全部已启用 -> 移除；否则 -> 设为启用）
static void ToggleAutoRunApps() {
    HWND lv = GetDlgItem(g_mainWnd, IDC_LIST);
    std::vector<size_t> rows;   // 应用索引
    std::vector<int> selRows;   // 列表行号（用于保留选中）
    int s = -1;
    while ((s = ListView_GetNextItem(lv, s, LVNI_SELECTED)) >= 0) {
        LVITEMW vi = {0};
        vi.mask = LVIF_PARAM;
        vi.iItem = s;
        ListView_GetItem(lv, &vi);
        rows.push_back((size_t)vi.lParam);
        selRows.push_back(s);
    }
    if (rows.empty()) return;
    bool allEnabled = true;
    for (size_t r : rows)
        if (r >= g_apps.size() || !g_apps[r].enabled) { allEnabled = false; break; }
    bool newVal = !allEnabled;
    for (size_t r : rows) {
        if (r >= g_apps.size()) continue;
        g_apps[r].enabled = newVal;
        if (newVal && g_apps[r].days <= 0) g_apps[r].days = 0x7F;
    }
    SaveApps();
    RefreshList();
    // 保留选中状态，便于继续批量操作
    for (int row : selRows) {
        LVITEMW st = {0};
        st.stateMask = LVIS_SELECTED;
        st.state = LVIS_SELECTED;
        SendMessageW(lv, LVM_SETITEMSTATE, (WPARAM)row, (LPARAM)&st);
    }
    UpdateButtons();
}

static LRESULT CALLBACK MainWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        g_mainWnd = hwnd;
        DWORD lvStyle = LVS_REPORT | LVS_SHOWSELALWAYS;
        HWND lv = Mk(hwnd, WC_LISTVIEWW, L"", lvStyle, 0, 0, 100, 100, IDC_LIST);
        ListView_SetExtendedListViewStyle(lv, LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES | LVS_EX_DOUBLEBUFFER);
        LVCOLUMNW col = {0};
        col.mask = LVCF_TEXT | LVCF_WIDTH | LVCF_SUBITEM;
        struct { const wchar_t* t; int w; } cols[] = {
            {L"#", 40}, {L"软件名称", 170}, {L"路径", 330}, {L"打开计划", 110}, {L"状态", 60},
        };
        for (int i = 0; i < 5; i++) {
            col.iSubItem = i;
            col.pszText = (LPWSTR)cols[i].t;
            col.cx = ScaleI(cols[i].w);
            ListView_InsertColumn(lv, i, &col);
        }
        Mk(hwnd, L"BUTTON", L"添加软件",   WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_ADD);
        Mk(hwnd, L"BUTTON", L"从索引添加", WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_ADDIDX);
        Mk(hwnd, L"BUTTON", L"编辑",       WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_EDIT);
        Mk(hwnd, L"BUTTON", L"删除",       WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_DEL);
        Mk(hwnd, L"BUTTON", L"立即启动",   WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_RUN);
        Mk(hwnd, L"BUTTON", L"设置开机启动", WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_AUTORUN);
        Mk(hwnd, L"STATIC", L"", 0, 0,0,10,10, IDC_STATUS);
        Mk(hwnd, L"STATIC", L"启动倒计时(秒):", 0, 0,0,10,10, 9100);
        HWND edT = Mk(hwnd, L"EDIT", L"", WS_TABSTOP | WS_BORDER | ES_NUMBER | ES_CENTER,
                      0,0,10,10, IDC_TIMEOUT);
        wchar_t tbuf[16];
        swprintf(tbuf, 16, L"%d", g_confirmSeconds);
        SetWindowTextW(edT, tbuf);
        Mk(hwnd, L"STATIC", L"回车或移开焦点保存 | 0 = 手动确认 | 最大 300 秒",
           0, 0,0,10,10, 9101);
        RefreshList();
        PostMessageW(hwnd, WM_SIZE, 0, 0);
        return 0;
    }
    case WM_SIZE: {
        int w = LOWORD(lp), h = HIWORD(lp);
        if (w > 0 && h > 0) LayoutMain(hwnd, w, h);
        // 自动调整“路径”列宽
        HWND lv = GetDlgItem(hwnd, IDC_LIST);
        RECT rc;
        GetClientRect(lv, &rc);
        int rest = ScaleI(40 + 170 + 110 + 60);
        int pathW = (rc.right - rc.left) - rest - ScaleI(4);
        if (pathW < ScaleI(120)) pathW = ScaleI(120);
        ListView_SetColumnWidth(lv, 2, pathW);
        return 0;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        switch (id) {
        case IDC_ADD:     ShowEditDlg(hwnd, -1); break;
        case IDC_ADDIDX:  ShowIndexDlg(hwnd); break;
        case IDC_EDIT: {
            HWND lv = GetDlgItem(hwnd, IDC_LIST);
            int sel = ListView_GetNextItem(lv, -1, LVNI_SELECTED);
            if (sel >= 0) {
                LVITEMW vi = {0};
                vi.mask = LVIF_PARAM;
                vi.iItem = sel;
                ListView_GetItem(lv, &vi);
                ShowEditDlg(hwnd, (int)vi.lParam);
            }
            break;
        }
        case IDC_DEL:    DoDelete(); break;
        case IDC_RUN:    DoRunSelected(); break;
        case IDC_AUTORUN: ToggleAutoRunApps(); break;
        case IDC_TIMEOUT:
            if (HIWORD(wp) == EN_KILLFOCUS) ApplyTimeoutFromEdit(hwnd);
            break;
        }
        return 0;
    }
    case WM_KEYDOWN: {
        // 在倒计时输入框中按回车 = 立即保存
        if (wp == VK_RETURN && GetFocus() == GetDlgItem(hwnd, IDC_TIMEOUT)) {
            ApplyTimeoutFromEdit(hwnd);
            return 0;
        }
        break;
    }
    case WM_NOTIFY: {
        NMHDR* nm = (NMHDR*)lp;
        if (nm->idFrom == IDC_LIST) {
            if (nm->code == NM_DBLCLK) {
                NMITEMACTIVATE* ia = (NMITEMACTIVATE*)lp;
                if (ia->iItem >= 0) {
                    ShowEditDlg(hwnd, (int)ia->lParam);
                }
            } else if (nm->code == LVN_ITEMCHANGED) {
                UpdateButtons();
            }
        }
        return 0;
    }
    case WM_DESTROY:
        g_mainWnd = NULL;
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

// ------------------------------------------------------------
// 编辑对话框
// ------------------------------------------------------------
static void LayoutEdit(HWND hwnd, int w, int h) {
    (void)h;
    int pad = ScaleI(18), labW = ScaleI(78), ch = ScaleI(24), gap = ScaleI(12);
    int cw = w - pad * 2;
    int y = pad + ScaleI(4);
    MoveWindow(GetDlgItem(hwnd, 9000), pad, y, labW, ch, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_E_NAME), pad + labW, y, cw - labW, ch, TRUE);
    y += ch + gap;
    MoveWindow(GetDlgItem(hwnd, 9002), pad, y, labW, ch, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_E_PATH), pad + labW, y, cw - labW - ScaleI(92), ch, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_E_BROWSE), pad + cw - ScaleI(86), y, ScaleI(86), ch, TRUE);
    y += ch + gap;
    MoveWindow(GetDlgItem(hwnd, IDC_E_ENABLE), pad + labW, y, ScaleI(180), ch, TRUE);
    y += ch + gap + ScaleI(6);
    MoveWindow(GetDlgItem(hwnd, 9001), pad, y, cw, ScaleI(56), TRUE);
    for (int i = 0; i < 7; i++)
        MoveWindow(GetDlgItem(hwnd, IDC_E_DOW0 + i), pad + ScaleI(10) + i * ScaleI(56),
                   y + ScaleI(24), ScaleI(54), ch, TRUE);
    y += ScaleI(56) + gap + ScaleI(6);
    MoveWindow(GetDlgItem(hwnd, IDC_E_OK), w - pad - ScaleI(176), y, ScaleI(80), ScaleI(28), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_E_CANCEL), w - pad - ScaleI(88), y, ScaleI(88), ScaleI(28), TRUE);
}

#define WM_APP_INITDATA (WM_APP + 1)

static void EditFillData(HWND hwnd) {
    int idx = (int)GetWindowLongPtrW(hwnd, GWLP_USERDATA);
    if (idx >= 0 && idx < (int)g_apps.size()) {
        const AppItem& it = g_apps[idx];
        SetWindowTextW(GetDlgItem(hwnd, IDC_E_NAME), it.name.c_str());
        SetWindowTextW(GetDlgItem(hwnd, IDC_E_PATH), it.path.c_str());
        CheckDlgButton(hwnd, IDC_E_ENABLE, it.enabled ? BST_CHECKED : BST_UNCHECKED);
        for (int i = 0; i < 7; i++)
            CheckDlgButton(hwnd, IDC_E_DOW0 + i, (it.days & (1 << i)) ? BST_CHECKED : BST_UNCHECKED);
    } else {
        CheckDlgButton(hwnd, IDC_E_ENABLE, BST_CHECKED);
        for (int i = 0; i < 7; i++) CheckDlgButton(hwnd, IDC_E_DOW0 + i, BST_CHECKED);
    }
}

static void SaveEdit(HWND hwnd) {
    std::wstring name = Trim(GetWndText(GetDlgItem(hwnd, IDC_E_NAME)));
    std::wstring path = Trim(GetWndText(GetDlgItem(hwnd, IDC_E_PATH)));
    if (name.empty()) { MessageBoxW(hwnd, L"请填写软件名称。", L"提示", MB_OK | MB_ICONWARNING); return; }
    if (path.empty() || !PathFileExistsW(path.c_str())) {
        MessageBoxW(hwnd, L"程序路径不存在，请重新选择。", L"提示", MB_OK | MB_ICONWARNING);
        return;
    }
    int days = 0;
    for (int i = 0; i < 7; i++)
        if (IsDlgButtonChecked(hwnd, IDC_E_DOW0 + i)) days |= (1 << i);
    if (days == 0) days = 0x7F;
    AppItem it;
    it.name = name;
    it.path = path;
    it.days = days;
    it.enabled = IsDlgButtonChecked(hwnd, IDC_E_ENABLE) ? true : false;
    int idx = (int)GetWindowLongPtrW(hwnd, GWLP_USERDATA);
    if (idx >= 0 && idx < (int)g_apps.size()) g_apps[idx] = it;
    else g_apps.push_back(it);
    SaveApps();
    RefreshList();
    DestroyWindow(hwnd);
}

static LRESULT CALLBACK EditDlgProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        Mk(hwnd, L"STATIC", L"软件名称:", 0, 0,0,10,10, 9000);
        Mk(hwnd, L"EDIT",   L"", ES_AUTOHSCROLL | WS_TABSTOP | WS_BORDER, 0,0,10,10, IDC_E_NAME);
        Mk(hwnd, L"STATIC", L"程序路径:", 0, 0,0,10,10, 9002);
        Mk(hwnd, L"EDIT",   L"", ES_AUTOHSCROLL | WS_TABSTOP | WS_BORDER, 0,0,10,10, IDC_E_PATH);
        Mk(hwnd, L"BUTTON", L"浏览...", WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_E_BROWSE);
        Mk(hwnd, L"BUTTON", L"启用该软件", BS_AUTOCHECKBOX | WS_TABSTOP, 0,0,10,10, IDC_E_ENABLE);
        Mk(hwnd, L"BUTTON", L"打开计划（星期）", BS_GROUPBOX, 0,0,10,10, 9001);
        static const wchar_t* dow[] = {L"周一",L"周二",L"周三",L"周四",L"周五",L"周六",L"周日"};
        for (int i = 0; i < 7; i++)
            Mk(hwnd, L"BUTTON", dow[i], BS_AUTOCHECKBOX | WS_TABSTOP, 0,0,10,10, IDC_E_DOW0 + i);
        Mk(hwnd, L"BUTTON", L"确定", WS_TABSTOP | BS_DEFPUSHBUTTON, 0,0,10,10, IDC_E_OK);
        Mk(hwnd, L"BUTTON", L"取消", WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_E_CANCEL);
        PostMessageW(hwnd, WM_SIZE, 0, 0);
        SetFocus(GetDlgItem(hwnd, IDC_E_NAME));
        return 0;
    }
    case WM_APP_INITDATA:
        EditFillData(hwnd);
        return 0;
    case WM_SIZE:
        if (LOWORD(lp) > 0) LayoutEdit(hwnd, LOWORD(lp), HIWORD(lp));
        return 0;
    case WM_CTLCOLORSTATIC:
        return (LRESULT)GetSysColorBrush(COLOR_BTNFACE);
    case WM_COMMAND: {
        int id = LOWORD(wp);
        if (id == IDC_E_BROWSE) {
            wchar_t buf[MAX_PATH] = {0};
            GetWindowTextW(GetDlgItem(hwnd, IDC_E_PATH), buf, MAX_PATH);
            wchar_t filter[] = L"程序 (*.exe)\0*.exe\0所有文件 (*.*)\0*.*\0";
            OPENFILENAMEW ofn = {0};
            ofn.lStructSize = sizeof(ofn);
            ofn.hwndOwner = hwnd;
            ofn.lpstrFilter = filter;
            ofn.lpstrFile = buf;
            ofn.nMaxFile = MAX_PATH;
            ofn.Flags = OFN_FILEMUSTEXIST | OFN_PATHMUSTEXIST | OFN_HIDEREADONLY;
            ofn.lpstrTitle = L"选择要打开的程序";
            if (GetOpenFileNameW(&ofn)) SetWindowTextW(GetDlgItem(hwnd, IDC_E_PATH), buf);
        } else if (id == IDC_E_OK) {
            SaveEdit(hwnd);
        } else if (id == IDC_E_CANCEL) {
            DestroyWindow(hwnd);
        }
        return 0;
    }
    case WM_CLOSE:
        DestroyWindow(hwnd);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static void ShowEditDlg(HWND parent, int index) {
    int ww = ScaleI(446), wh = ScaleI(286);
    RECT pr = {0};
    if (parent) GetWindowRect(parent, &pr);
    int x = pr.left + (((pr.right - pr.left) - ww) / 2);
    int y = pr.top  + (((pr.bottom - pr.top) - wh) / 2);
    HWND dlg = CreateWindowExW(WS_EX_DLGMODALFRAME, EDIT_CLASS,
                               index >= 0 ? L"编辑软件" : L"添加软件",
                               WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
                               x, y, ww, wh, parent, NULL, g_hInst, NULL);
    if (!dlg) return;
    SetWindowLongPtrW(dlg, GWLP_USERDATA, (LONG_PTR)index);
    SendMessageW(dlg, WM_APP_INITDATA, 0, 0);
    ShowWindow(dlg, SW_SHOW);
    UpdateWindow(dlg);
    RunModalLoop(dlg, parent);
}

// ------------------------------------------------------------
// 索引对话框
// ------------------------------------------------------------
struct IndexCtx {
    std::vector<FoundApp> cache;
    std::set<std::wstring> checked;
    std::wstring filter;
    bool updating = false;
};

static IndexCtx g_idx;

static bool AppPathExists(const std::wstring& p) {
    std::wstring lp = LowerCopy(p);
    for (const AppItem& a : g_apps)
        if (LowerCopy(a.path) == lp) return true;
    return false;
}

static void IndexRescan(HWND hwnd) {
    HWND list = GetDlgItem(hwnd, IDC_I_LIST);
    g_idx.updating = true;
    SendMessageW(list, WM_SETREDRAW, FALSE, 0);
    ListView_DeleteAllItems(list);
    for (size_t i = 0; i < g_idx.cache.size(); i++) {
        const FoundApp& f = g_idx.cache[i];
        if (!g_idx.filter.empty() && !ContainsI(f.name, g_idx.filter) && !ContainsI(f.path, g_idx.filter))
            continue;
        LVITEMW vi = {0};
        vi.mask = LVIF_TEXT | LVIF_PARAM;
        vi.iItem = (int)ListView_GetItemCount(list);
        vi.pszText = (LPWSTR)f.name.c_str();
        vi.lParam = (LPARAM)i;
        int row = ListView_InsertItem(list, &vi);
        if (row < 0) continue;
        ListView_SetItemText(list, row, 1, (LPWSTR)f.path.c_str());
        if (g_idx.checked.count(LowerCopy(f.path)))
            ListView_SetCheckState(list, row, TRUE);
    }
    SendMessageW(list, WM_SETREDRAW, TRUE, 0);
    InvalidateRect(list, NULL, FALSE);
    g_idx.updating = false;
    wchar_t buf[128];
    swprintf(buf, 128, L"索引到 %d 个软件，当前显示 %d 个",
             (int)g_idx.cache.size(), ListView_GetItemCount(list));
    SetWindowTextW(GetDlgItem(hwnd, IDC_I_COUNT), buf);
}

static void IndexAddChecked(HWND hwnd) {
    HWND list = GetDlgItem(hwnd, IDC_I_LIST);
    int n = ListView_GetItemCount(list);
    int added = 0, skipped = 0;
    for (int i = 0; i < n; i++) {
        if (!ListView_GetCheckState(list, i)) continue;
        LVITEMW vi = {0};
        vi.mask = LVIF_PARAM;
        vi.iItem = i;
        ListView_GetItem(list, &vi);
        const FoundApp& f = g_idx.cache[(size_t)vi.lParam];
        if (AppPathExists(f.path)) { skipped++; continue; }
        AppItem it;
        it.name = f.name;
        it.path = f.path;
        it.days = 0x7F;
        it.enabled = true;
        g_apps.push_back(it);
        added++;
    }
    if (added > 0) SaveApps();
    RefreshList();
    wchar_t msg[160];
    swprintf(msg, 160, L"已添加 %d 个软件%s", added,
             skipped > 0 ? L"（重复项已跳过）。" : L"。");
    MessageBoxW(hwnd, msg, L"从索引添加", MB_OK | MB_ICONINFORMATION);
    if (added > 0) DestroyWindow(hwnd);
}

static void LayoutIndex(HWND hwnd, int w, int h) {
    int pad = ScaleI(14), ch = ScaleI(26);
    MoveWindow(GetDlgItem(hwnd, IDC_I_SEARCH), pad, pad, ScaleI(330), ch, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_I_REFISH), pad + ScaleI(338), pad, ScaleI(96), ch, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_I_COUNT), pad + ScaleI(442), pad,
               w - pad - ScaleI(442) - pad, ch, TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_I_LIST), pad, pad + ch + ScaleI(10),
               w - pad * 2, h - (pad + ch + ScaleI(10)) - ScaleI(50), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_I_ADD), w - pad - ScaleI(110), h - ScaleI(38),
               ScaleI(110), ScaleI(28), TRUE);
}

static LRESULT CALLBACK IndexDlgProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        HWND se = Mk(hwnd, L"EDIT", L"", ES_AUTOHSCROLL | WS_TABSTOP | WS_BORDER, 0,0,10,10, IDC_I_SEARCH);
        SendMessageW(se, EM_SETCUEBANNER, (WPARAM)TRUE, (LPARAM)L"搜索软件名 / 路径...");
        Mk(hwnd, L"BUTTON", L"刷新索引", WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_I_REFISH);
        Mk(hwnd, L"STATIC", L"正在扫描...", 0, 0,0,10,10, IDC_I_COUNT);
        HWND lv = Mk(hwnd, WC_LISTVIEWW, L"", LVS_REPORT | LVS_SHOWSELALWAYS, 0,0,10,10, IDC_I_LIST);
        ListView_SetExtendedListViewStyle(lv, LVS_EX_CHECKBOXES | LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES | LVS_EX_DOUBLEBUFFER);
        LVCOLUMNW col = {0};
        col.mask = LVCF_TEXT | LVCF_WIDTH | LVCF_SUBITEM;
        col.iSubItem = 0; col.pszText = (LPWSTR)L"软件名称"; col.cx = ScaleI(230);
        ListView_InsertColumn(lv, 0, &col);
        col.iSubItem = 1; col.pszText = (LPWSTR)L"程序路径"; col.cx = ScaleI(380);
        ListView_InsertColumn(lv, 1, &col);
        Mk(hwnd, L"BUTTON", L"添加勾选项", WS_TABSTOP | BS_DEFPUSHBUTTON, 0,0,10,10, IDC_I_ADD);

        g_idx.cache = ScanInstalledApps();
        IndexRescan(hwnd);
        PostMessageW(hwnd, WM_SIZE, 0, 0);
        return 0;
    }
    case WM_SIZE: {
        int w = LOWORD(lp), h = HIWORD(lp);
        if (w > 0) {
            LayoutIndex(hwnd, w, h);
            HWND lv = GetDlgItem(hwnd, IDC_I_LIST);
            RECT rc;
            GetClientRect(lv, &rc);
            ListView_SetColumnWidth(lv, 1, (rc.right - rc.left) - ScaleI(230) - ScaleI(4));
        }
        return 0;
    }
    case WM_CTLCOLORSTATIC:
        return (LRESULT)GetSysColorBrush(COLOR_BTNFACE);
    case WM_NOTIFY: {
        NMHDR* nm = (NMHDR*)lp;
        if (nm->idFrom == IDC_I_LIST && nm->code == LVN_ITEMCHANGED && !g_idx.updating) {
            NMLISTVIEW* nml = (NMLISTVIEW*)lp;
            UINT oldS = nml->uOldState & LVIS_STATEIMAGEMASK;
            UINT newS = nml->uNewState & LVIS_STATEIMAGEMASK;
            if ((nml->uChanged & LVIF_STATE) && nml->iItem >= 0 && oldS != newS) {
                wchar_t path[MAX_PATH] = {0};
                ListView_GetItemText(nm->hwndFrom, nml->iItem, 1, path, MAX_PATH);
                bool nowChecked = ((newS >> 12) - 1) == 1;
                if (nowChecked) g_idx.checked.insert(LowerCopy(path));
                else g_idx.checked.erase(LowerCopy(path));
            }
        }
        return 0;
    }
    case WM_COMMAND: {
        int id = LOWORD(wp);
        if (id == IDC_I_REFISH) {
            SetWindowTextW(GetDlgItem(hwnd, IDC_I_COUNT), L"正在扫描...");
            g_idx.cache = ScanInstalledApps();
            IndexRescan(hwnd);
        } else if (id == IDC_I_ADD) {
            IndexAddChecked(hwnd);
        } else if (id == IDC_I_SEARCH && HIWORD(wp) == EN_CHANGE) {
            g_idx.filter = GetWndText(GetDlgItem(hwnd, IDC_I_SEARCH));
            IndexRescan(hwnd);
        }
        return 0;
    }
    case WM_CLOSE:
        DestroyWindow(hwnd);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

static void ShowIndexDlg(HWND parent) {
    int ww = ScaleI(680), wh = ScaleI(500);
    RECT pr = {0};
    if (parent) GetWindowRect(parent, &pr);
    int x = pr.left + (((pr.right - pr.left) - ww) / 2);
    int y = pr.top  + (((pr.bottom - pr.top) - wh) / 2);
    HWND dlg = CreateWindowExW(WS_EX_DLGMODALFRAME, INDEX_CLASS, L"从本机索引添加",
                               WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
                               x, y, ww, wh, parent, NULL, g_hInst, NULL);
    if (!dlg) return;
    ShowWindow(dlg, SW_SHOW);
    UpdateWindow(dlg);
    RunModalLoop(dlg, parent);
}

// ------------------------------------------------------------
// 开机确认窗口（--auto）
// ------------------------------------------------------------
struct ConfirmCtx {
    std::vector<AppItem> items;
    int remain = 0;
    bool hasTimer = false;
};

static ConfirmCtx g_conf;

static void ConfirmLaunch(HWND hwnd) {
    HWND lv = GetDlgItem(hwnd, IDC_C_LIST);
    int n = ListView_GetItemCount(lv);
    int started = 0;
    for (int i = 0; i < n; i++) {
        if (!ListView_GetCheckState(lv, i)) continue;
        LVITEMW vi = {0};
        vi.mask = LVIF_PARAM;
        vi.iItem = i;
        ListView_GetItem(lv, &vi);
        if (LaunchApp(g_conf.items[(size_t)vi.lParam].path)) started++;
    }
    (void)started;
    DestroyWindow(hwnd);
}

static void ConfirmUpdateLabel(HWND hwnd) {
    wchar_t buf[160];
    if (g_conf.hasTimer && g_conf.remain > 0)
        swprintf(buf, 160, L"%d 秒后将自动启动勾选的软件...", g_conf.remain);
    else if (g_conf.hasTimer)
        swprintf(buf, 160, L"正在启动...");
    else
        swprintf(buf, 160, L"请勾选需要启动的软件，点击“启动”。");
    SetWindowTextW(GetDlgItem(hwnd, IDC_C_LABEL), buf);
    HWND ok = GetDlgItem(hwnd, IDC_C_OK);
    if (g_conf.hasTimer && g_conf.remain > 0) {
        wchar_t bt[64];
        swprintf(bt, 64, L"启动 (%d)", g_conf.remain);
        SetWindowTextW(ok, bt);
    } else {
        SetWindowTextW(ok, L"启动");
    }
}

static void LayoutConfirm(HWND hwnd, int w, int h) {
    int pad = ScaleI(16);
    MoveWindow(GetDlgItem(hwnd, 6001), pad, pad, w - pad * 2, ScaleI(40), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_C_LIST), pad, pad + ScaleI(46),
               w - pad * 2, h - ScaleI(46) - ScaleI(120), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_C_LABEL), pad, h - ScaleI(70), w - pad * 2, ScaleI(24), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_C_OK), w - ScaleI(230), h - ScaleI(40), ScaleI(104), ScaleI(30), TRUE);
    MoveWindow(GetDlgItem(hwnd, IDC_C_CANCEL), w - ScaleI(116), h - ScaleI(40), ScaleI(100), ScaleI(30), TRUE);
}

static LRESULT CALLBACK ConfirmWndProc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    switch (msg) {
    case WM_CREATE: {
        Mk(hwnd, L"STATIC",
           L"以下软件计划在今天自动打开，请核对并勾选需要启动的项目：",
           0, 0,0,10,10, 6001);
        HWND lv = Mk(hwnd, WC_LISTVIEWW, L"", LVS_REPORT | LVS_SHOWSELALWAYS, 0,0,10,10, IDC_C_LIST);
        ListView_SetExtendedListViewStyle(lv, LVS_EX_CHECKBOXES | LVS_EX_FULLROWSELECT | LVS_EX_GRIDLINES | LVS_EX_DOUBLEBUFFER);
        LVCOLUMNW col = {0};
        col.mask = LVCF_TEXT | LVCF_WIDTH | LVCF_SUBITEM;
        col.iSubItem = 0; col.pszText = (LPWSTR)L"软件名称"; col.cx = ScaleI(190);
        ListView_InsertColumn(lv, 0, &col);
        col.iSubItem = 1; col.pszText = (LPWSTR)L"程序路径"; col.cx = ScaleI(330);
        ListView_InsertColumn(lv, 1, &col);
        for (size_t i = 0; i < g_conf.items.size(); i++) {
            wchar_t idx[16];
            swprintf(idx, 16, L"%d", (int)(i + 1));
            LVITEMW vi = {0};
            vi.mask = LVIF_TEXT | LVIF_PARAM;
            vi.iItem = (int)i;
            vi.pszText = idx;
            vi.lParam = (LPARAM)i;
            int row = ListView_InsertItem(lv, &vi);
            if (row < 0) continue;
            ListView_SetItemText(lv, row, 1, (LPWSTR)g_conf.items[i].name.c_str());
            ListView_SetItemText(lv, row, 2, (LPWSTR)g_conf.items[i].path.c_str());
            ListView_SetCheckState(lv, row, TRUE);
        }
        Mk(hwnd, L"STATIC", L"", 0, 0,0,10,10, IDC_C_LABEL);
        Mk(hwnd, L"BUTTON", L"启动", WS_TABSTOP | BS_DEFPUSHBUTTON, 0,0,10,10, IDC_C_OK);
        Mk(hwnd, L"BUTTON", L"取消", WS_TABSTOP | BS_PUSHBUTTON, 0,0,10,10, IDC_C_CANCEL);

        if (g_confirmSeconds > 0) {
            g_conf.hasTimer = true;
            g_conf.remain = g_confirmSeconds;
            SetTimer(hwnd, 1, 1000, NULL);
        }
        ConfirmUpdateLabel(hwnd);
        PostMessageW(hwnd, WM_SIZE, 0, 0);
        return 0;
    }
    case WM_TIMER:
        if (wp == 1 && g_conf.hasTimer && g_conf.remain > 0) {
            g_conf.remain--;
            if (g_conf.remain <= 0) { ConfirmLaunch(hwnd); return 0; }
            ConfirmUpdateLabel(hwnd);
        }
        return 0;
    case WM_SIZE: {
        int w = LOWORD(lp), h = HIWORD(lp);
        if (w > 0) {
            LayoutConfirm(hwnd, w, h);
            HWND lv = GetDlgItem(hwnd, IDC_C_LIST);
            RECT rc;
            GetClientRect(lv, &rc);
            ListView_SetColumnWidth(lv, 1, (rc.right - rc.left) - ScaleI(190) - ScaleI(4));
        }
        return 0;
    }
    case WM_CTLCOLORSTATIC:
        return (LRESULT)GetSysColorBrush(COLOR_BTNFACE);
    case WM_COMMAND: {
        int id = LOWORD(wp);
        if (id == IDC_C_OK) ConfirmLaunch(hwnd);
        else if (id == IDC_C_CANCEL) DestroyWindow(hwnd);
        return 0;
    }
    case WM_CLOSE:
        DestroyWindow(hwnd);
        return 0;
    case WM_DESTROY:
        if (g_conf.hasTimer) KillTimer(hwnd, 1);
        PostQuitMessage(0);
        return 0;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

// ------------------------------------------------------------
// 窗口类注册与入口
// ------------------------------------------------------------
static bool RegisterOneClass(const wchar_t* cls, WNDPROC proc, HBRUSH bg) {
    WNDCLASSW wc = {0};
    wc.lpfnWndProc = proc;
    wc.hInstance = g_hInst;
    wc.hCursor = LoadCursorW(NULL, (LPCWSTR)IDC_ARROW);
    wc.hIcon = LoadIconW(g_hInst, (LPCWSTR)1);
    wc.hbrBackground = bg;
    wc.lpszClassName = cls;
    return RegisterClassW(&wc) != 0;
}

static void RegisterClasses() {
    RegisterOneClass(MAIN_CLASS, MainWndProc, (HBRUSH)(COLOR_WINDOW + 1));
    RegisterOneClass(EDIT_CLASS, EditDlgProc, (HBRUSH)(COLOR_BTNFACE + 1));
    RegisterOneClass(INDEX_CLASS, IndexDlgProc, (HBRUSH)(COLOR_BTNFACE + 1));
    RegisterOneClass(CONFIRM_CLASS, ConfirmWndProc, (HBRUSH)(COLOR_WINDOW + 1));
}

static void CreateFonts() {
    UINT dpi = GetDpiForSystem();
    if (dpi < 96) dpi = 96;
    g_scale = dpi / 96.0;
    g_font = CreateFontW(-MulDiv(9, (int)dpi, 72), 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
                         DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
                         CLEARTYPE_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Microsoft YaHei UI");
}

int WINAPI wWinMain(HINSTANCE hInst, HINSTANCE, PWSTR, int) {
    g_hInst = hInst;
    SetProcessDPIAware();   // 避免 DPI 虚拟化导致布局/列宽被系统二次缩放
    if (FAILED(CoInitializeEx(NULL, COINIT_APARTMENTTHREADED | COINIT_DISABLE_OLE1DDE)))
        return 1;
    INITCOMMONCONTROLSEX icc = {sizeof(icc), ICC_LISTVIEW_CLASSES | ICC_STANDARD_CLASSES};
    InitCommonControlsEx(&icc);
    CreateFonts();
    RegisterClasses();
    LoadConfig();
    LoadApps();

    int argc = 0;
    LPWSTR* argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    bool autoMode = false, installMode = false, removeMode = false;
    if (argv) {
        for (int i = 1; i < argc; i++) {
            if (wcscmp(argv[i], L"--auto") == 0) autoMode = true;
            else if (wcscmp(argv[i], L"--install-autorun") == 0) installMode = true;
            else if (wcscmp(argv[i], L"--remove-autorun") == 0) removeMode = true;
        }
        LocalFree(argv);
    }

    if (installMode || removeMode) {
        bool ok;
        if (installMode) ok = InstallAutoRun();
        else { RemoveAutoRun(); ok = true; }
        MessageBoxW(NULL,
                    ok ? (installMode ? L"开机自启已设置。" : L"开机自启已移除。")
                       : L"操作失败。",
                    L"AutoOpenApps",
                    MB_OK | (ok ? MB_ICONINFORMATION : MB_ICONERROR));
        CoUninitialize();
        return ok ? 0 : 1;
    }

    if (autoMode) {
        int today = TodayBit();
        std::vector<AppItem> todays;
        for (const AppItem& a : g_apps)
            if (a.enabled && (a.days & today)) todays.push_back(a);
        if (todays.empty()) { CoUninitialize(); return 0; }
        g_conf.items = todays;
        int ww = ScaleI(560), wh = ScaleI(430);
        HWND w = CreateWindowExW(WS_EX_TOPMOST, CONFIRM_CLASS,
                                 L"AutoOpenApps - 开机启动确认",
                                 WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU,
                                 CW_USEDEFAULT, CW_USEDEFAULT, ww, wh,
                                 NULL, NULL, g_hInst, NULL);
        if (!w) { CoUninitialize(); return 1; }
        // 居中显示
        RECT dr = {0};
        SystemParametersInfoW(SPI_GETWORKAREA, 0, &dr, 0);
        SetWindowPos(w, NULL,
                     dr.left + ((dr.right - dr.left) - ww) / 2,
                     dr.top + ((dr.bottom - dr.top) - wh) / 2,
                     0, 0, SWP_NOSIZE | SWP_NOZORDER);
        ShowWindow(w, SW_SHOW);
        SetForegroundWindow(w);
        MSG m;
        while (GetMessageW(&m, NULL, 0, 0) > 0) {
            TranslateMessage(&m);
            DispatchMessageW(&m);
        }
        CoUninitialize();
        return 0;
    }

    HANDLE mutex = CreateMutexW(NULL, FALSE, L"AutoOpenApps_SingleInstance");
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        HWND h = FindWindowW(MAIN_CLASS, NULL);
        if (h) {
            if (IsIconic(h)) ShowWindow(h, SW_RESTORE);
            SetForegroundWindow(h);
        }
        if (mutex) CloseHandle(mutex);
        CoUninitialize();
        return 0;
    }

    HWND w = CreateWindowExW(0, MAIN_CLASS, L"AutoOpenApps 软件管理",
                             WS_OVERLAPPEDWINDOW,
                             CW_USEDEFAULT, CW_USEDEFAULT, ScaleI(940), ScaleI(620),
                             NULL, NULL, g_hInst, NULL);
    if (!w) { CoUninitialize(); return 1; }
    ShowWindow(w, SW_SHOW);
    UpdateWindow(w);
    MSG m;
    while (GetMessageW(&m, NULL, 0, 0) > 0) {
        if (IsDialogMessageW(w, &m)) continue;
        TranslateMessage(&m);
        DispatchMessageW(&m);
    }
    if (mutex) CloseHandle(mutex);
    CoUninitialize();
    return 0;
}
