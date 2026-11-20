# -*- coding: utf-8 -*-
"""AutoOpenApps - browser UI pages (stdlib http server renders these)."""

CONFIRM_TEXT = ("开机软件清单待确认：勾选要打开的软件后点“确认启动”；"
                "不需要的取消勾选即可；点“取消”则本次不打开任何软件。")

_MANAGER_PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>软件启动助手</title>
<style>
:root{--accent:#2563eb;--danger:#dc2626;--text:#1f2937;--muted:#6b7280;--bg:#f5f6f8;--card:#ffffff;--line:#e5e7eb}
*{box-sizing:border-box}body{margin:0;font-family:"Microsoft YaHei",system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--text)}
.wrap{max-width:860px;margin:0 auto;padding:24px 16px 48px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--muted);font-size:13px;margin-bottom:18px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.toolbar{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-bottom:14px}
button{font:inherit;padding:8px 14px;border-radius:8px;border:1px solid var(--line);background:#fff;cursor:pointer}
button:hover{border-color:var(--accent);color:var(--accent)}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff}
button.primary:hover{opacity:.9;color:#fff}
button.danger{color:var(--danger);border-color:#f3c1c1}
button.mini{padding:4px 10px;font-size:12px}
button:disabled{opacity:.5;cursor:default}
.flex{flex:1}
label.chk{display:flex;gap:6px;align-items:center;font-size:14px;cursor:pointer}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{border-bottom:1px solid var(--line);padding:8px 6px;text-align:left;vertical-align:middle}
th{background:#f0f2f5;color:#374151;font-weight:600}
td.path{color:var(--muted);word-break:break-all;max-width:340px}
.rowbtns{display:flex;gap:6px}
#editor{margin-top:16px;border-top:2px dashed var(--line);padding-top:14px}
#editor.hidden,.hidden{display:none}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px 14px;margin:10px 0}
.grid label{display:flex;flex-direction:column;gap:4px;font-size:13px;color:#374151}
.grid label.wide{grid-column:1/-1}
.grid input{font:inherit;padding:7px 9px;border:1px solid var(--line);border-radius:8px}
.grid input:focus{outline:2px solid #bfdbfe;border-color:var(--accent)}
.pathline{display:flex;gap:8px}.pathline input{flex:1}
.hint{color:var(--muted);font-size:13px;min-height:18px;margin-top:12px;white-space:pre-wrap}
footer{color:#9ca3af;font-size:12px;margin-top:22px;line-height:1.7;word-break:break-all}
.empty{color:var(--muted);text-align:center;padding:22px 0}
</style></head><body><div class="wrap">
<h1>软件启动助手</h1>
<div class="sub">在这里维护要自动打开的软件清单；开机时会先弹出确认页，勾选后再打开。</div>
<div class="card">
  <div class="toolbar">
    <button id="btnAdd">＋ 添加软件</button>
    <button id="btnLaunch" class="primary">▶ 一键启动（全部启用项）</button>
    <label class="chk"><input type="checkbox" id="chkAuto"> 开机自启</label>
    <span class="flex"></span>
    <button id="btnQuit" class="danger">退出程序</button>
  </div>
  <table><thead><tr><th style="width:52px">启用</th><th style="width:110px">名称</th><th>程序路径</th><th style="width:70px">延迟(秒)</th><th style="width:110px">启动参数</th><th style="width:120px">操作</th></tr></thead>
  <tbody id="rows"></tbody></table>
  <div id="empty" class="empty hidden">清单为空：点“＋ 添加软件”添加第一个应用。</div>
  <div id="editor" class="hidden">
    <h3 id="edTitle" style="margin:4px 0 8px;font-size:15px">添加软件</h3>
    <div class="grid">
      <label>名称<input id="edName" type="text" placeholder="如：示例浏览器"></label>
      <label>延迟(秒)<input id="edDelay" type="number" min="0" max="300" value="0"></label>
      <label class="wide">程序路径（exe 完整路径）<div class="pathline"><input id="edPath" type="text" placeholder="C:\\Program Files\\Example\\App.exe"><button id="btnBrowse" type="button">浏览…</button></div></label>
      <label class="wide">启动参数（可留空）<input id="edArgs" type="text" placeholder="如：--new-window"></label>
    </div>
    <div class="toolbar" style="margin:0">
      <button id="edSave" class="primary">保存</button>
      <button id="edCancel">取消</button>
    </div>
  </div>
  <p class="hint" id="msg"></p>
</div>
<footer>配置文件：__CFGFILE__<br>说明：同名进程已在运行的应用会被自动跳过，避免重复开窗。关闭本页面后程序约 2 分钟内自动退出，也可点“退出程序”立即退出。</footer>
</div>
<script>
var cfg = {apps: []};
var editing = -1;
function $(s){return document.querySelector(s)}
async function api(path, body){
  var opt = body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : undefined;
  var r = await fetch(path, opt);
  return r.json();
}
function esc(s){return String(s==null?'':s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;')}
function render(){
  var tb = $('#rows'); tb.innerHTML = '';
  $('#empty').classList.toggle('hidden', cfg.apps.length > 0);
  cfg.apps.forEach(function(a, i){
    var tr = document.createElement('tr');
    tr.innerHTML = '<td><input type="checkbox" data-act="en" data-i="'+i+'" '+(a.enabled?'checked':'')+'></td>'
      + '<td>'+esc(a.name)+'</td><td class="path">'+esc(a.path)+'</td>'
      + '<td>'+esc(a.delay)+'</td><td class="path">'+esc(a.args||'')+'</td>'
      + '<td><div class="rowbtns"><button class="mini" data-act="edit" data-i="'+i+'">编辑</button>'
      + '<button class="mini danger" data-act="del" data-i="'+i+'">删除</button></div></td>';
    tb.appendChild(tr);
  });
}
async function save(){ await api('/api/config', cfg); }
function msg(m){ $('#msg').textContent = m; }
$('#rows').addEventListener('change', async function(e){
  var t = e.target, i = t.getAttribute('data-i');
  if (t.getAttribute('data-act') === 'en'){ cfg.apps[i].enabled = t.checked; await save(); }
});
$('#rows').addEventListener('click', async function(e){
  var t = e.target, act = t.getAttribute('data-act'), i = t.getAttribute('data-i');
  if (act === 'edit'){ openEditor(parseInt(i,10)); }
  if (act === 'del'){
    if (!confirm('确定删除“'+cfg.apps[i].name+'”？')) return;
    cfg.apps.splice(parseInt(i,10),1); await save(); render(); msg('已删除。');
  }
});
function openEditor(i){
  editing = i;
  var a = i >= 0 ? cfg.apps[i] : {name:'',path:'',delay:0,args:''};
  $('#edTitle').textContent = i >= 0 ? '编辑：'+a.name : '添加软件';
  $('#edName').value = a.name; $('#edPath').value = a.path;
  $('#edDelay').value = a.delay || 0; $('#edArgs').value = a.args || '';
  $('#editor').classList.remove('hidden');
  $('#edName').focus();
}
function closeEditor(){ $('#editor').classList.add('hidden'); editing = -1; }
$('#btnAdd').onclick = function(){ openEditor(-1); };
$('#edCancel').onclick = closeEditor;
$('#btnBrowse').onclick = async function(){
  var r = await api('/api/browse');
  if (r && r.path) $('#edPath').value = r.path;
};
$('#edSave').onclick = async function(){
  var name = $('#edName').value.trim(), path = $('#edPath').value.trim();
  var delay = parseInt($('#edDelay').value,10) || 0, args = $('#edArgs').value.trim();
  if (!path){ msg('请填写程序路径。'); return; }
  var item = {name: name || path.split('\\\\').pop().replace(/\\.exe$/i,''), path: path, delay: delay, args: args, enabled: true};
  if (editing >= 0){ item.enabled = cfg.apps[editing].enabled; cfg.apps[editing] = item; }
  else { cfg.apps.push(item); }
  await save(); render(); closeEditor(); msg('已保存。');
};
$('#btnLaunch').onclick = async function(){
  var b = $('#btnLaunch'); b.disabled = true; msg('正在启动…');
  var r = await api('/api/launch', {all: true});
  b.disabled = false;
  var lines = ['已启动 '+r.launched.length+' 个'];
  if (r.skipped.length) lines.push('跳过已运行 '+r.skipped.length+' 个');
  if (r.failed.length) lines.push('失败 '+r.failed.length+' 个：' + r.failed.map(function(f){return f[0]+'（'+f[1]+'）'}).join('；'));
  msg(lines.join('；') + (r.launched.length ? '\\n已打开：' + r.launched.join('、') : ''));
};
$('#chkAuto').onchange = async function(){
  var r = await api('/api/autostart', {enable: $('#chkAuto').checked});
  msg(r.message || '');
  if (!r.ok) $('#chkAuto').checked = !$('#chkAuto').checked;
};
$('#btnQuit').onclick = async function(){
  await api('/api/shutdown');
  document.querySelector('.card').innerHTML = '<h2 style="margin:8px 0">已退出，可关闭此页面。</h2>';
};
setInterval(function(){ fetch('/api/ping').catch(function(){}); }, 5000);
(async function(){
  var data = await api('/api/config');
  cfg.apps = data.apps || [];
  $('#chkAuto').checked = !!data.autostart;
  render();
})();
</script></body></html>"""

_CONFIRM_PAGE = """<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>开机启动确认</title>
<style>
:root{--accent:#2563eb;--danger:#dc2626;--text:#1f2937;--muted:#6b7280;--bg:#f5f6f8;--card:#fff;--line:#e5e7eb}
*{box-sizing:border-box}body{margin:0;font-family:"Microsoft YaHei",system-ui,Segoe UI,sans-serif;background:var(--bg);color:var(--text);display:flex;min-height:100vh;align-items:center;justify-content:center;padding:24px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;box-shadow:0 4px 18px rgba(0,0,0,.08);width:100%;max-width:560px;padding:22px 24px}
h1{font-size:19px;margin:0 0 8px}.desc{color:var(--muted);font-size:13px;line-height:1.7;margin-bottom:14px}
.list{border:1px solid var(--line);border-radius:10px;overflow:hidden;margin-bottom:16px;max-height:320px;overflow-y:auto}
.item{display:flex;gap:10px;align-items:center;padding:10px 14px;border-bottom:1px solid var(--line);cursor:pointer}
.item:last-child{border-bottom:0}.item:hover{background:#f8fafc}
.item input{width:17px;height:17px;accent-color:var(--accent)}
.item .nm{font-size:14px;font-weight:600}.item .pt{font-size:12px;color:var(--muted);word-break:break-all}
.btns{display:flex;gap:10px}
button{font:inherit;padding:10px 18px;border-radius:9px;border:1px solid var(--line);background:#fff;cursor:pointer;flex:1}
button.primary{background:var(--accent);border-color:var(--accent);color:#fff;font-weight:600}
button.cancel{color:var(--danger)}
.result{font-size:14px;line-height:1.8;white-space:pre-wrap}
footer{color:#9ca3af;font-size:12px;margin-top:14px}
.empty{color:var(--muted);padding:18px 0;text-align:center}
</style></head><body><div class="card">
<h1>☑ 开机启动确认</h1>
<div class="desc">__CONFIRMTEXT__</div>
<div id="content"><div class="empty">正在读取清单…</div></div>
<div class="btns hidden" id="btns">
  <button class="primary" id="ok">确认启动</button>
  <button class="cancel" id="no">取消</button>
</div>
<div class="result hidden" id="result"></div>
<footer>关闭本页面后程序约 2 分钟内自动退出。</footer>
</div>
<script>
function $(s){return document.querySelector(s)}
async function api(path, body){
  var opt = body ? {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)} : undefined;
  var r = await fetch(path, opt); return r.json();
}
var apps = [];
function render(){
  var box = $('#content'); box.innerHTML = '';
  if (!apps.length){
    box.innerHTML = '<div class="empty">清单为空：没有待启动的软件。<br>可打开“软件启动助手”添加。</div>';
    $('#btns').classList.add('hidden'); return;
  }
  apps.forEach(function(a, i){
    var lab = document.createElement('label');
    lab.className = 'item';
    lab.innerHTML = '<input type="checkbox" data-i="'+i+'" checked><span><span class="nm">'+a.name+'</span><br><span class="pt">'+a.path+'</span></span>';
    box.appendChild(lab);
  });
  $('#btns').classList.remove('hidden');
}
$('#ok').onclick = async function(){
  var sel = [];
  document.querySelectorAll('#content input[type=checkbox]').forEach(function(c){
    if (c.checked) sel.push(apps[parseInt(c.getAttribute('data-i'),10)].path);
  });
  if (!sel.length){ alert('请至少勾选一个软件，或点“取消”。'); return; }
  var r = await api('/api/launch', {paths: sel});
  var lines = ['已启动 '+r.launched.length+' 个'];
  if (r.skipped.length) lines.push('跳过已运行 '+r.skipped.length+' 个');
  if (r.failed.length) lines.push('失败 '+r.failed.length+' 个：'+r.failed.map(function(f){return f[0]+'（'+f[1]+'）'}).join('；'));
  if (r.launched.length) lines.push('已打开：'+r.launched.join('、'));
  $('#result').textContent = lines.join('\\n');
  $('#result').classList.remove('hidden'); $('#btns').classList.add('hidden'); $('#content').classList.add('hidden');
};
$('#no').onclick = async function(){
  await api('/api/cancel');
  $('#result').textContent = '已取消：本次不打开任何软件。';
  $('#result').classList.remove('hidden'); $('#btns').classList.add('hidden'); $('#content').classList.add('hidden');
};
setInterval(function(){ fetch('/api/ping').catch(function(){}); }, 5000);
(async function(){
  var data = await api('/api/config');
  apps = (data.apps || []).filter(function(a){ return a.enabled; });
  render();
})();
</script></body></html>"""


def manager_page(cfg_file):
    return _MANAGER_PAGE.replace("__CFGFILE__", cfg_file)


def confirm_page():
    return _CONFIRM_PAGE.replace("__CONFIRMTEXT__", CONFIRM_TEXT)
