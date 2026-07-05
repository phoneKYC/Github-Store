"""
خادم Webhook + لوحة التحكم (Dashboard)
يعمل مع FastAPI ويُستخدم عند النشر على منصات مثل Railway
"""
import os
import hashlib
import logging

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

from bot.config import config
from bot.database import (
    init_db,
    get_dashboard_stats,
    get_recent_searches,
    get_recent_downloads,
    get_users_list,
    get_daily_activity,
    get_top_repos,
)
from bot.handlers.commands import start, help_command
from bot.handlers.auth import login, logout
from bot.handlers.search import search
from bot.handlers.callbacks import button_router
from telegram.ext import CommandHandler, CallbackQueryHandler

logger = logging.getLogger(__name__)

app = FastAPI(title="GitHub Store Bot")


def _get_admin_hash() -> str:
    """تجزئة كلمة مرور الـ Admin (لا تُخزن نصاً صريحاً)"""
    pwd = os.environ.get("ADMIN_PASSWORD", "admin123")
    return hashlib.sha256(pwd.encode()).hexdigest()


def _check_admin(request: Request) -> bool:
    """التحقق من مصادقة Admin عبر session cookie"""
    session = request.cookies.get("admin_session", "")
    return session == _get_admin_hash()


# ══════════════════════════════════════════════
#  DASHBOARD PAGES
# ══════════════════════════════════════════════

@app.get("/admin", response_class=HTMLResponse)
async def admin_login_page():
    """صفحة تسجيل دخول الداشبورد"""
    return DASHBOARD_LOGIN_HTML


@app.post("/admin/login")
async def admin_login(request: Request):
    """التحقق من كلمة مرور Admin"""
    form = await request.form()
    password = str(form.get("password", ""))
    if hashlib.sha256(password.encode()).hexdigest() == _get_admin_hash():
        response = Response(status_code=302, headers={"Location": "/admin/dashboard"})
        response.set_cookie("admin_session", _get_admin_hash(), httponly=True, max_age=86400)
        return response
    return HTMLResponse(DASHBOARD_LOGIN_HTML.replace("<!-- ERROR -->", '<p style="color:#ef4444">كلمة المرور غير صحيحة</p>'))


@app.get("/admin/dashboard", response_class=HTMLResponse)
async def admin_dashboard(request: Request):
    """صفحة الداشبورد الرئيسية"""
    if not _check_admin(request):
        return Response(status_code=302, headers={"Location": "/admin"})
    return DASHBOARD_HTML


# ══════════════════════════════════════════════
#  DASHBOARD API (JSON)
# ══════════════════════════════════════════════

@app.get("/admin/api/stats")
async def api_stats(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    stats = await get_dashboard_stats()
    return JSONResponse(stats)


@app.get("/admin/api/users")
async def api_users(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    users = await get_users_list()
    return JSONResponse(users)


@app.get("/admin/api/searches")
async def api_searches(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    searches = await get_recent_searches()
    return JSONResponse(searches)


@app.get("/admin/api/downloads")
async def api_downloads(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    downloads = await get_recent_downloads()
    return JSONResponse(downloads)


@app.get("/admin/api/activity")
async def api_activity(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    activity = await get_daily_activity()
    return JSONResponse(activity)


@app.get("/admin/api/top-repos")
async def api_top_repos(request: Request):
    if not _check_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    repos = await get_top_repos()
    return JSONResponse(repos)


@app.post("/admin/logout")
async def admin_logout():
    response = Response(status_code=302, headers={"Location": "/admin"})
    response.delete_cookie("admin_session")
    return response


# ══════════════════════════════════════════════
#  TELEGRAM BOT (Webhook + Health)
# ══════════════════════════════════════════════

@app.on_event("startup")
async def startup_event():
    from telegram.ext import Application

    application = Application.builder().token(config.BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("login", login))
    application.add_handler(CommandHandler("logout", logout))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CallbackQueryHandler(button_router))

    await application.initialize()
    await application.start()
    await init_db()

    if config.WEBHOOK_URL:
        await application.bot.set_webhook(
            url=config.WEBHOOK_URL,
            secret_token=config.WEBHOOK_SECRET if config.WEBHOOK_SECRET else None,
            allowed_updates=["message", "callback_query"],
        )
        logger.info(f"تم ضبط Webhook: {config.WEBHOOK_URL}")

    app.state.application = application


@app.on_event("shutdown")
async def shutdown_event():
    application = getattr(app.state, "application", None)
    if application:
        await application.shutdown()


@app.post("/webhook")
async def webhook_handler(request: Request) -> Response:
    from telegram import Update

    if config.WEBHOOK_SECRET:
        sig = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if sig != config.WEBHOOK_SECRET:
            return Response(status_code=403)

    application = app.state.application
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return Response(status_code=200)


@app.get("/health")
async def health_check() -> dict:
    return {"status": "ok", "service": "github-store-bot"}


# ══════════════════════════════════════════════
#  DASHBOARD HTML
# ══════════════════════════════════════════════

DASHBOARD_LOGIN_HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitHub Store Bot — Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:#0f172a;min-height:100vh;display:flex;align-items:center;justify-content:center;color:#e2e8f0}
.card{background:#1e293b;border-radius:16px;padding:48px;width:380px;text-align:center;box-shadow:0 20px 60px rgba(0,0,0,.5)}
.card h1{font-size:24px;margin-bottom:8px;color:#f8fafc}
.card p{color:#94a3b8;margin-bottom:32px;font-size:14px}
input{width:100%;padding:14px 20px;border-radius:10px;border:2px solid #334155;background:#0f172a;color:#f8fafc;font-size:16px;outline:none;transition:border .2s}
input:focus{border-color:#8b5cf6}
button{width:100%;padding:14px;border-radius:10px;border:none;background:linear-gradient(135deg,#8b5cf6,#6366f1);color:#fff;font-size:16px;font-weight:700;cursor:pointer;margin-top:16px;transition:transform .15s}
button:hover{transform:scale(1.02)}
<!-- ERROR -->
</style>
</head>
<body>
<div class="card">
<h1>🏪 GitHub Store Bot</h1>
<p>لوحة التحكم — أدخل كلمة المرور</p>
<form method="POST" action="/admin/login">
<input type="password" name="password" placeholder="كلمة المرور" required autofocus>
<button type="submit">دخول</button>
</form>
</div>
</body>
</html>"""


DASHBOARD_HTML = """<!DOCTYPE html>
<html dir="rtl" lang="ar">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>GitHub Store Bot — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4"></script>
<style>
:root{--bg:#0f172a;--card:#1e293b;--border:#334155;--text:#e2e8f0;--muted:#94a3b8;--accent:#8b5cf6;--green:#22c55e;--red:#ef4444;--blue:#3b82f6;--yellow:#eab308}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI',Tahoma,sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
header{background:var(--card);border-bottom:1px solid var(--border);padding:16px 32px;display:flex;justify-content:space-between;align-items:center}
header h1{font-size:18px}.header-right a{color:var(--muted);text-decoration:none;font-size:14px;margin-right:16px}
header a:hover{color:var(--accent)}
.container{max-width:1200px;margin:0 auto;padding:24px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:16px;margin-bottom:24px}
.stat-card{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;text-align:center}
.stat-card .num{font-size:32px;font-weight:800;background:linear-gradient(135deg,var(--accent),var(--blue));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.stat-card .label{font-size:13px;color:var(--muted);margin-top:4px}
.charts{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px}
.chart-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px}
.chart-box h3{font-size:15px;margin-bottom:12px;color:var(--muted)}
canvas{max-height:250px}
.tables{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.table-box{background:var(--card);border:1px solid var(--border);border-radius:12px;padding:20px;max-height:400px;overflow-y:auto}
.table-box h3{font-size:15px;margin-bottom:12px;color:var(--muted)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:right;color:var(--muted);padding:8px;border-bottom:1px solid var(--border);font-weight:600}
td{padding:8px;border-bottom:1px solid var(--border)}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:11px;font-weight:600}
.badge-ok{background:#166534;color:#bbf7d0}.badge-err{background:#7f1d1d;color:#fecaca}
.badge-link{background:#1e3a5f;color:#93c5fd}.badge-doc{background:#14532d;color:#86efac}
::-webkit-scrollbar{width:6px}::-webkit-scrollbar-track{background:var(--bg)}::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
@media(max-width:768px){.charts,.tables{grid-template-columns:1fr}.stats{grid-template-columns:1fr 1fr}}
</style>
</head>
<body>
<header>
<h1>🏪 GitHub Store Bot — لوحة التحكم</h1>
<div class="header-right">
<a href="/" onclick="location.reload()">تحديث</a>
<a href="/admin/logout">خروج</a>
</div>
</header>
<div class="container">
<div class="stats" id="stats"></div>
<div class="charts">
<div class="chart-box"><h3>النشاط اليومي (بحث)</h3><canvas id="activityChart"></canvas></div>
<div class="chart-box"><h3>أكثر المستودعات بحثا</h3><canvas id="reposChart"></canvas></div>
</div>
<div class="tables">
<div class="table-box"><h3>آخر عمليات البحث</h3><table id="searchTable"><thead><tr><th>المستخدم</th><th>الاستعلام</th><th>المستودع</th><th>الحالة</th></tr></thead><tbody></tbody></table></div>
<div class="table-box"><h3>آخر التحميلات</h3><table id="dlTable"><thead><tr><th>المستخدم</th><th>المستودع</th><th>الملف</th><th>الطريقة</th></tr></thead><tbody></tbody></table></div>
</div>
</div>
<script>
const API='';const h=t=>document.getElementById(t);
function fmtSize(b){if(b<1024)return b+' B';if(b<1048576)return(b/1024).toFixed(1)+' KB';return(b/1048576).toFixed(1)+' MB'}

async function load(){
  const s=await(await fetch(API+'/admin/api/stats')).json();
  h('stats').innerHTML=`
    <div class="stat-card"><div class="num">${s.total_users}</div><div class="label">إجمالي المستخدمين</div></div>
    <div class="stat-card"><div class="num">${s.linked_users}</div><div class="label">حسابات مرتبطة</div></div>
    <div class="stat-card"><div class="num">${s.active_24h}</div><div class="label">نشطين (24س)</div></div>
    <div class="stat-card"><div class="num">${s.total_searches}</div><div class="label">عمليات البحث</div></div>
    <div class="stat-card"><div class="num">${s.total_downloads}</div><div class="label">تحميلات</div></div>
    <div class="stat-card"><div class="num">${fmtSize(s.total_bytes)}</div><div class="label">حجم التحميلات</div></div>
    <div class="stat-card"><div class="num">${s.total_errors}</div><div class="label">أخطاء</div></div>
    <div class="stat-card"><div class="num">${s.weekly_searches}</div><div class="label">بحث/أسبوع</div></div>`;

  // Activity chart
  const act=await(await fetch(API+'/admin/api/activity')).json();
  new Chart(h('activityChart'),{type:'bar',data:{labels:act.map(r=>r.day),datasets:[
    {label:'باحثون',data:act.map(r=>r.users),backgroundColor:'#8b5cf6',borderRadius:6},
    {label:'عمليات بحث',data:act.map(r=>r.searches),backgroundColor:'#3b82f6',borderRadius:6}
  ]},options:{responsive:true,plugins:{legend:{labels:{color:'#94a3b8',font:{size:11}}}},scales:{x:{ticks:{color:'#64748b',font:{size:10}},grid:{color:'#1e293b'}},y:{ticks:{color:'#64748b'},grid:{color:'#1e293b'}}}}});

  // Top repos chart
  const repos=await(await fetch(API+'/admin/api/top-repos')).json();
  new Chart(h('reposChart'),{type:'doughnut',data:{labels:repos.map(r=>r.repo_found),datasets:[{data:repos.map(r=>r.count),backgroundColor:['#8b5cf6','#3b82f6','#22c55e','#eab308','#ef4444','#06b6d4','#f97316','#ec4899','#14b8a6','#a855f7']}]},options:{responsive:true,plugins:{legend:{position:'right',labels:{color:'#94a3b8',font:{size:10},boxWidth:12}}}}});

  // Search table
  const searches=await(await fetch(API+'/admin/api/searches')).json();
  h('searchTable').querySelector('tbody').innerHTML=searches.map(r=>`<tr>
    <td>${r.user_id}</td><td>${r.query}</td><td>${r.repo_found||'—'}</td>
    <td><span class="badge ${r.status==='success'?'badge-ok':'badge-err'}">${r.status}</span></td>
  </tr>`).join('');

  // Downloads table
  const dls=await(await fetch(API+'/admin/api/downloads')).json();
  h('dlTable').querySelector('tbody').innerHTML=dls.map(r=>`<tr>
    <td>${r.user_id}</td><td>${r.repo_name}</td><td>${r.file_name}</td>
    <td><span class="badge ${r.delivery_method==='document'?'badge-doc':'badge-link'}">${r.delivery_method}</span></td>
  </tr>`).join('');
}
load();
</script>
</body>
</html>"""