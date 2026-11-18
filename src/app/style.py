"""
Phần "thiết kế" của giao diện: CSS bổ sung, chuyển sáng/tối, dải giá chạy ngang, hình minh họa trang chủ,
sơ đồ luồng dữ liệu và khung "Dữ liệu" ở thanh bên.

Màu chủ đạo: tím (#6d3fd9) và vàng gold (#ffd54a -> #f2a900). Màu cơ bản của từng giao diện (nền, chữ,
viền) đặt trong .streamlit/config.toml ([theme.light] và [theme.dark]); file này thêm những gì config không
làm được: thẻ có nền chuyển màu và bóng đổ, hiệu ứng xuất hiện/rê chuột, khối hero chuyển màu chậm...

Thẻ nội dung được đánh dấu bằng `key` của st.container. Khóa bắt đầu bằng "card" -> Streamlit gắn lớp CSS
"st-key-card..." -> CSS bên dưới tạo kiểu. Ký tự thứ 5 của khóa chọn tông màu nền:
    cardp_ tím · cardg_ vàng · cardr_ đỏ nhạt · cardo_ cam nhạt · cardk_ xanh lá nhạt · cardv_ tím nhạt

Hình minh họa là SVG tự vẽ (không dùng ảnh có bản quyền của người khác). Mọi hiệu ứng tự tắt khi máy bật
chế độ "giảm chuyển động" (prefers-reduced-motion).
"""
from __future__ import annotations

from html import escape

PURPLE, GOLD = "#6d3fd9", "#f2a900"

_VARS = {
    False: """
  --card-bg: #ffffff; --tint-p: #f3ecff; --tint-g: #fff4d2; --tint-r: #fff0f1; --tint-o: #fff4e2;
  --tint-k: #e9f9ef; --tint-v: #f4effe; --border: #ece6f8; --shadow: rgba(76, 42, 160, .08);
  --shadow-hover: rgba(76, 42, 160, .18); --text: #1f1937; --muted: #625c78; --hero-a: #f1e8ff;
  --hero-b: #fff6df; --chip-bg: #ffffff; --chip-border: #e3d8fb; --chip-text: #4b2aa6; --soft: #f7f3ff; --slogan: #8a5a00;
""",
    True: """
  --card-bg: #1b1630; --tint-p: #261d47; --tint-g: #2d2614; --tint-r: #34171f; --tint-o: #33250f;
  --tint-k: #12302a; --tint-v: #231c3d; --border: #2f2848; --shadow: rgba(0, 0, 0, .35);
  --shadow-hover: rgba(138, 102, 242, .28); --text: #ece8f7; --muted: #b3abcc; --hero-a: #211940;
  --hero-b: #2b2213; --chip-bg: #1f1933; --chip-border: #3a2f63; --chip-text: #cdbbff; --soft: #1f1933; --slogan: #ffd54a;
""",
}

_CSS = """
/* ---------- thẻ nội dung ---------- */
[class*="st-key-card"] {
  background:
    linear-gradient(90deg, #6d3fd9, #b04fd6 55%, #f2a900) top / 100% 3px no-repeat,
    linear-gradient(155deg, var(--card-bg) 35%, var(--tint) 100%);
  --tint: var(--tint-v);
  border: 1px solid var(--border); border-radius: 20px; padding: 18px 20px 16px 20px;
  box-shadow: 0 4px 18px var(--shadow);
  transition: transform .2s ease, box-shadow .2s ease, border-color .2s ease;
  animation: rise .55s cubic-bezier(.2, .7, .2, 1) both;
}
[class*="st-key-card"]:hover {
  transform: translateY(-4px); border-color: #b9a2ff; box-shadow: 0 14px 34px var(--shadow-hover);
}
[class*="st-key-cardp_"] { --tint: var(--tint-p); }
[class*="st-key-cardg_"] { --tint: var(--tint-g); }
[class*="st-key-cardr_"] { --tint: var(--tint-r); }
[class*="st-key-cardo_"] { --tint: var(--tint-o); }
[class*="st-key-cardk_"] { --tint: var(--tint-k); }
[class*="st-key-cardv_"] { --tint: var(--tint-v); }
[data-testid="stColumn"]:nth-child(2) [class*="st-key-card"] { animation-delay: .07s; }
[data-testid="stColumn"]:nth-child(3) [class*="st-key-card"] { animation-delay: .14s; }
[data-testid="stColumn"]:nth-child(4) [class*="st-key-card"] { animation-delay: .21s; }
@keyframes rise { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }

/* ---------- ô kết luận ---------- */
[class*="st-key-verdict"] {
  border-radius: 26px; padding: 26px 30px; border: 1px solid var(--border);
  background:
    radial-gradient(circle at 92% 12%, rgba(255, 213, 74, .30), transparent 34%),
    radial-gradient(circle at 4% 96%, rgba(109, 63, 217, .16), transparent 40%),
    linear-gradient(135deg, var(--hero-a) 0%, var(--card-bg) 75%);
  background-size: 140% 140%; animation: rise .5s ease both, drift 14s ease-in-out infinite alternate;
  box-shadow: 0 8px 28px var(--shadow);
}
.verdict-kicker { color: var(--muted); font-size: .85rem; font-weight: 600; letter-spacing: .02em; }
.verdict-label { font-size: 2.2rem; font-weight: 800; color: var(--text); line-height: 1.15; margin: .35rem 0 .5rem 0; }
.verdict-pill {
  display: inline-flex; align-items: center; gap: 6px; border-radius: 999px; padding: 4px 12px;
  font-weight: 700; font-size: .85rem;
}
.pill-danger { background: rgba(220, 38, 38, .12); color: #dc2626; }
.pill-warning { background: rgba(232, 134, 12, .14); color: #c26a00; }
.pill-good { background: rgba(22, 163, 74, .13); color: #15803d; }
.verdict-text { color: var(--muted); margin-top: .5rem; }

/* ---------- khối hero trang chủ ---------- */
.st-key-hero {
  border-radius: 34px; padding: 38px 40px 30px 44px; border: 1px solid var(--border);
  background:
    radial-gradient(circle at 86% 16%, rgba(255, 213, 74, .38), transparent 36%),
    radial-gradient(circle at 6% 94%, rgba(109, 63, 217, .24), transparent 42%),
    linear-gradient(135deg, var(--hero-a) 0%, var(--hero-b) 100%);
  background-size: 160% 160%; animation: drift 16s ease-in-out infinite alternate;
  box-shadow: 0 10px 40px var(--shadow);
}
@keyframes drift { from { background-position: 0% 30%; } to { background-position: 100% 70%; } }
.hero-kicker { color: #6d3fd9; font-weight: 800; letter-spacing: .16em; font-size: .78rem; text-transform: uppercase; }
.hero-title { font-size: 3.1rem; font-weight: 800; line-height: 1.12; color: var(--text); margin: .4rem 0 .9rem 0; }
.glow, .gold-text {
  background: linear-gradient(90deg, #6d3fd9 0%, #b04fd6 35%, #f2a900 65%, #ffd54a 80%, #6d3fd9 100%);
  background-size: 220% auto; -webkit-background-clip: text; background-clip: text; color: transparent;
  animation: shine 5s linear infinite;
}
@keyframes shine { to { background-position: 220% center; } }
.hero-slogan {
  display: inline-block; font-size: 1.15rem; font-weight: 700; font-style: italic; margin: -.2rem 0 .9rem 0;
  padding: 6px 16px; border-radius: 999px; color: var(--slogan);
  background: linear-gradient(90deg, rgba(255, 213, 74, .35), rgba(242, 169, 0, .18));
  border: 1px solid rgba(242, 169, 0, .45);
}
.hero-sub { font-size: 1.05rem; color: var(--muted); line-height: 1.65; max-width: 35rem; }
.chips { margin-top: 1rem; }
.chip {
  display: inline-block; background: var(--chip-bg); border: 1px solid var(--chip-border); border-radius: 999px;
  padding: 5px 14px; margin: 0 8px 8px 0; font-size: .84rem; color: var(--chip-text); font-weight: 600;
  transition: transform .2s ease;
}
.chip:hover { transform: translateY(-2px); }
.chip b { color: #e09b00; }
.ms {
  font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; font-size: 26px; line-height: 1;
  display: inline-block; white-space: nowrap; -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga';
}

/* ---------- thẻ tính năng, bước, tiêu đề mục ---------- */
.feature-icon {
  width: 50px; height: 50px; border-radius: 16px; display: flex; align-items: center; justify-content: center;
  color: #ffffff; margin-bottom: .3rem; background: linear-gradient(135deg, #8a5cf0, #5a2fc2);
  box-shadow: 0 8px 18px rgba(109, 63, 217, .30); transition: transform .3s ease;
}
.feature-icon.gold { background: linear-gradient(135deg, #ffd54a, #f2a900); box-shadow: 0 8px 18px rgba(242, 169, 0, .32); }
[class*="st-key-card"]:hover .feature-icon { transform: rotate(-8deg) scale(1.08); }
.step-no {
  width: 36px; height: 36px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center;
  background: linear-gradient(135deg, #ffd54a, #f2a900); color: #2b2100; font-weight: 800; margin-right: .55rem;
  box-shadow: 0 6px 14px rgba(242, 169, 0, .30);
}
.section-title { font-size: 1.55rem; font-weight: 800; color: var(--text); margin: 1.7rem 0 .25rem 0; }

/* ---------- sơ đồ luồng dữ liệu (trang Phương pháp) ---------- */
.flow { display: flex; flex-wrap: wrap; align-items: stretch; gap: 10px; margin: .4rem 0 .6rem 0; }
.flow-step {
  flex: 1 1 140px; background: var(--card-bg); border: 1px solid var(--border); border-radius: 18px;
  padding: 14px 14px 12px 14px; box-shadow: 0 4px 14px var(--shadow); animation: rise .5s ease both;
}
.flow-step:nth-child(3) { animation-delay: .08s; } .flow-step:nth-child(5) { animation-delay: .16s; }
.flow-step:nth-child(7) { animation-delay: .24s; } .flow-step:nth-child(9) { animation-delay: .32s; }
.flow-step .ms { color: #6d3fd9; font-size: 28px; }
.flow-step b { display: block; color: var(--text); margin: .3rem 0 .2rem 0; }
.flow-step span.t { color: var(--muted); font-size: .84rem; line-height: 1.45; }
.flow-arrow { display: flex; align-items: center; color: #e09b00; font-size: 22px; }

/* ---------- dải giá chạy ngang ---------- */
.ticker {
  overflow: hidden; white-space: nowrap; border-radius: 16px; border: 1px solid var(--border);
  background: var(--card-bg); box-shadow: 0 2px 10px var(--shadow); padding: 9px 0; margin-bottom: .4rem;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent);
          mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent);
}
.ticker-track { display: inline-flex; gap: 34px; padding-left: 34px; animation: ticker 60s linear infinite; }
.ticker:hover .ticker-track { animation-play-state: paused; }
@keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.tick { font-size: .9rem; color: var(--text); }
.tick b { margin-right: 6px; }
.tick .tag { border-radius: 6px; padding: 1px 7px; margin-left: 6px; font-weight: 700; font-size: .8rem; }
.tick .up { background: rgba(22, 163, 74, .14); color: #16a34a; }
.tick .down { background: rgba(220, 38, 38, .13); color: #dc2626; }
.tick .flat { background: rgba(242, 169, 0, .16); color: #c98a00; }
.tick-label { font-size: .78rem; color: #6d3fd9; font-weight: 800; letter-spacing: .06em; }

/* ---------- thanh bên ---------- */
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: linear-gradient(90deg, #6d3fd9, #8a5cf0) !important; border-radius: 12px;
  box-shadow: 0 6px 16px rgba(109, 63, 217, .30);
}
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #ffffff !important; }
[data-testid="stSidebarNav"] a { border-radius: 12px; transition: transform .15s ease; }
[data-testid="stSidebarNav"] a:hover { transform: translateX(3px); }
.data-box {
  background: var(--card-bg); border: 1px solid var(--border); border-radius: 16px; padding: 12px 14px;
  box-shadow: 0 3px 12px var(--shadow); font-size: .84rem; color: var(--text);
}
.db-title { font-weight: 800; margin-bottom: 6px; }
.db-row { display: flex; align-items: center; gap: 8px; margin: 4px 0; }
.db-sub { color: var(--muted); font-size: .76rem; margin-top: 6px; }
.dot { width: 9px; height: 9px; border-radius: 999px; flex: none; }
.dot.violet { background: #6d3fd9; } .dot.green { background: #16a34a; box-shadow: 0 0 0 0 rgba(22,163,74,.5); animation: ping 2s infinite; }
.dot.orange { background: #e8860c; } .dot.red { background: #dc2626; } .dot.gray { background: #a39cb8; }
@keyframes ping { 0% { box-shadow: 0 0 0 0 rgba(22,163,74,.45); } 70% { box-shadow: 0 0 0 7px rgba(22,163,74,0); } 100% { box-shadow: 0 0 0 0 rgba(22,163,74,0); } }

/* ---------- nút, khung mở rộng, bảng ---------- */
[data-testid="stBaseButton-primary"] {
  background: linear-gradient(135deg, #8a5cf0, #5a2fc2) !important; border: none !important;
  box-shadow: 0 8px 20px rgba(109, 63, 217, .32); transition: transform .15s ease, box-shadow .15s ease;
}
[data-testid="stBaseButton-primary"]:hover { transform: translateY(-2px); box-shadow: 0 12px 26px rgba(109, 63, 217, .42); }
[data-testid="stBaseButton-secondary"] { transition: transform .15s ease; }
[data-testid="stBaseButton-secondary"]:hover { transform: translateY(-2px); }
[data-testid="stExpander"] details {
  border-radius: 18px; border: 1px solid var(--border); background: var(--card-bg); box-shadow: 0 3px 12px var(--shadow);
}
[data-testid="stTable"] table { border-radius: 14px; overflow: hidden; }
[data-testid="stPageLink"] a { border-radius: 12px; }
h1 { letter-spacing: -0.02em; }

/* chọn sáng/tối bằng mục "Cài đặt" của ứng dụng, nên ẩn mục chọn giao diện trong menu mặc định */
[data-testid^="stMainMenuItem-theme"] { display: none !important; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
"""


def theme_css(dark: bool) -> str:
    """Toàn bộ CSS bổ sung cho giao diện sáng hoặc tối."""
    return f"<style>:root {{{_VARS[dark]}}}\n{_CSS}</style>"


def theme_sync_script(dark: bool) -> str:
    """Đồng bộ giao diện sáng/tối của Streamlit với lựa chọn ở mục Cài đặt (mặc định: sáng).

    Streamlit không có lệnh Python để đổi giao diện, nên đoạn script nhỏ này bấm hộ mục Light/Dark trong menu
    mặc định (đã được ẩn khỏi người dùng). Chỉ chạy khi giao diện hiện tại khác lựa chọn.
    """
    want = "Dark" if dark else "Light"
    return f"""<script>
(function () {{
  const want = "{want}";
  const current = JSON.parse(localStorage.getItem("stActiveTheme-/-v2") || '"System"');
  if (current === want) return;
  let doc = document;
  try {{ if (window.parent && window.parent.document) doc = window.parent.document; }} catch (e) {{}}
  const menu = doc.querySelector('[data-testid="stMainMenu"] button') || doc.querySelector('[data-testid="stMainMenu"]');
  if (!menu) return;
  menu.click();
  setTimeout(function () {{
    const item = doc.querySelector('[data-testid="stMainMenuItem-theme-' + want + '"]');
    if (item) item.click();
    setTimeout(function () {{
      if (doc.querySelector('[data-testid="stMainMenuPopover"]')) menu.click();
    }}, 60);
  }}, 60);
}})();
</script>"""


# ---------------------------------------------------------------- khung "Dữ liệu" ở thanh bên

def data_panel_html(rows: list[tuple[str, str]], note: str) -> str:
    """rows: (màu chấm: violet/green/orange/red/gray, nội dung)."""
    body = "".join(f'<div class="db-row"><span class="dot {color}"></span><span>{escape(text)}</span></div>'
                   for color, text in rows)
    return f'<div class="data-box"><div class="db-title">Dữ liệu</div>{body}<div class="db-sub">{escape(note)}</div></div>'


# ---------------------------------------------------------------- dải giá chạy ngang

def _vn(value: float, digits: int) -> str:
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def ticker_html(items: list[tuple[str, float, float]], session_label: str) -> str:
    """Dải giá chạy ngang. items: (tên, giá/điểm, % thay đổi so với phiên trước, dạng 0.012 = 1,2%)."""
    parts = []
    for name, value, change in items:
        if change != change:  # NaN
            tag = ""
        else:
            kind = "up" if change > 0 else ("down" if change < 0 else "flat")
            arrow = {"up": "▲", "down": "▼", "flat": "■"}[kind]
            tag = f'<span class="tag {kind}">{arrow} {_vn(abs(change) * 100, 2)}%</span>'
        digits = 2 if name.upper().startswith("VN") else 0
        parts.append(f'<span class="tick"><b>{escape(name)}</b>{_vn(value, digits)}{tag}</span>')
    head = f'<span class="tick-label">{escape(session_label)}</span>'
    track = head + "".join(parts)
    # nhân đôi nội dung để vòng chạy liền mạch (dịch -50% là quay lại đúng điểm đầu)
    return f'<div class="ticker"><div class="ticker-track">{track}{track}</div></div>'


# ---------------------------------------------------------------- sơ đồ luồng dữ liệu

FLOW_STEPS = [
    ("cloud_download", "SSI FastConnect API", "Giá theo phiên, khối ngoại, room, VN-Index, ngành ICB"),
    ("cleaning_services", "Làm sạch", "Bỏ dòng trùng, thiếu, giá ≤ 0; gắn cờ bất thường; giờ Việt Nam"),
    ("database", "Kho SQLite", "Lưu theo phiên, cập nhật phần mới, nhật ký từng lần tải"),
    ("calculate", "Tính toán", "Tập trung, thanh khoản, biến động, beta, VaR, giảm sàn"),
    ("monitor_heart", "Kết luận", "So với ngưỡng có nguồn, giải thích và gợi ý nên làm gì"),
]


def flow_html() -> str:
    cells = []
    for i, (icon, title, text) in enumerate(FLOW_STEPS):
        if i:
            cells.append('<div class="flow-arrow"><span class="ms">arrow_forward</span></div>')
        cells.append(f'<div class="flow-step"><span class="ms">{icon}</span><b>{title}</b>'
                     f'<span class="t">{text}</span></div>')
    return f'<div class="flow">{"".join(cells)}</div>'


# ---------------------------------------------------------------- hình minh họa trang chủ (SVG tự vẽ)

_HERO_SVG = """<svg viewBox="0 0 600 470" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Minh họa: thẻ sức khỏe danh mục với biểu đồ vành khuyên, đường nhịp tim, đồng xu và khiên bảo vệ">
  <style>
    .float-a { animation: floaty 6s ease-in-out infinite; }
    .float-b { animation: floaty 7s ease-in-out infinite reverse; }
    .float-c { animation: floaty 5s ease-in-out infinite; animation-delay: -2s; }
    @keyframes floaty { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }
    .spin { transform-box: fill-box; transform-origin: center; animation: spin 30s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .flip { transform-box: fill-box; transform-origin: center; animation: flip 5s ease-in-out infinite; }
    @keyframes flip { 0%, 70%, 100% { transform: scaleX(1); } 80% { transform: scaleX(.12); } 90% { transform: scaleX(1); } }
    .seg { animation: seg 1.4s ease-out both; }
    .seg2 { animation-delay: .35s; } .seg3 { animation-delay: .7s; }
    @keyframes seg { from { stroke-dasharray: 0 377; } }
    .pulse { stroke-dasharray: 460; stroke-dashoffset: 460; animation: draw 4.5s ease-in-out infinite; }
    @keyframes draw { 0% { stroke-dashoffset: 460; opacity: 1; } 55% { stroke-dashoffset: 0; opacity: 1; }
                      85% { stroke-dashoffset: 0; opacity: 0; } 100% { stroke-dashoffset: 460; opacity: 0; } }
    .bar { transform-box: fill-box; transform-origin: bottom; animation: grow 3.2s ease-in-out infinite alternate; }
    .b2 { animation-delay: -.8s; } .b3 { animation-delay: -1.6s; } .b4 { animation-delay: -2.4s; }
    @keyframes grow { from { transform: scaleY(.55); } to { transform: scaleY(1); } }
    .twinkle { transform-box: fill-box; transform-origin: center; animation: twinkle 2.6s ease-in-out infinite; }
    .tw2 { animation-delay: -.9s; } .tw3 { animation-delay: -1.7s; }
    @keyframes twinkle { 0%, 100% { opacity: .25; transform: scale(.6); } 50% { opacity: 1; transform: scale(1.1); } }
    .breathe { transform-box: fill-box; transform-origin: center; animation: breathe 2.4s ease-in-out infinite; }
    @keyframes breathe { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.12); } }
    .glowy { animation: glowy 6s ease-in-out infinite; }
    @keyframes glowy { 0%, 100% { opacity: .18; } 50% { opacity: .34; } }
  </style>
  <defs>
    <linearGradient id="gPurple" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#9a6dff"/><stop offset="1" stop-color="#5a2fc2"/>
    </linearGradient>
    <linearGradient id="gGold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffe27a"/><stop offset=".55" stop-color="#ffc21a"/><stop offset="1" stop-color="#f2a900"/>
    </linearGradient>
    <linearGradient id="gLine" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#6d3fd9"/><stop offset="1" stop-color="#f2a900"/>
    </linearGradient>
    <filter id="shadow" x="-25%" y="-25%" width="150%" height="160%">
      <feDropShadow dx="0" dy="12" stdDeviation="14" flood-color="#4b2aa6" flood-opacity="0.18"/>
    </filter>
  </defs>

  <circle class="glowy" cx="455" cy="105" r="110" fill="#ffc21a"/>
  <circle class="glowy" cx="150" cy="360" r="95" fill="#6d3fd9" style="animation-delay:-3s"/>

  <!-- vòng quỹ đạo -->
  <g class="spin"><ellipse cx="300" cy="245" rx="235" ry="185" fill="none" stroke="#b9a2ff" stroke-width="2"
     stroke-dasharray="4 12" opacity="0.55"/></g>

  <!-- thẻ chính -->
  <g filter="url(#shadow)"><rect x="150" y="90" width="320" height="285" rx="30" fill="CARD"/></g>
  <rect x="180" y="118" width="130" height="13" rx="6.5" fill="LINE"/>
  <rect x="180" y="140" width="86" height="11" rx="5.5" fill="LINE2"/>
  <g transform="translate(245 240) rotate(-90)">
    <circle r="60" fill="none" stroke="LINE2" stroke-width="22"/>
    <circle class="seg" r="60" fill="none" stroke="url(#gPurple)" stroke-width="22" stroke-dasharray="170 377" stroke-linecap="round"/>
    <circle class="seg seg2" r="60" fill="none" stroke="url(#gGold)" stroke-width="22" stroke-dasharray="95 377"
            stroke-dashoffset="-178" stroke-linecap="round"/>
    <circle class="seg seg3" r="60" fill="none" stroke="#1a9e8f" stroke-width="22" stroke-dasharray="60 377"
            stroke-dashoffset="-281" stroke-linecap="round"/>
  </g>
  <g class="breathe">
    <circle cx="245" cy="240" r="33" fill="INNER"/>
    <path d="M233 240 l8 8 l16 -17" fill="none" stroke="#16a34a" stroke-width="5.5" stroke-linecap="round" stroke-linejoin="round"/>
  </g>
  <rect x="335" y="195" width="108" height="11" rx="5.5" fill="LINE"/>
  <rect x="335" y="214" width="76" height="11" rx="5.5" fill="url(#gGold)"/>
  <rect x="335" y="246" width="108" height="11" rx="5.5" fill="LINE"/>
  <rect x="335" y="265" width="58" height="11" rx="5.5" fill="url(#gPurple)"/>
  <polyline class="pulse" points="172,340 236,340 256,312 278,364 300,322 316,340 448,340"
            fill="none" stroke="url(#gLine)" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- thẻ nhỏ: đường đi lên có điểm chạy -->
  <g class="float-b">
    <g filter="url(#shadow)"><rect x="18" y="168" width="150" height="96" rx="22" fill="CARD"/></g>
    <path id="mini" d="M36 238 C 60 232, 70 214, 92 218 S 128 200, 150 186" fill="none" stroke="url(#gLine)"
          stroke-width="4" stroke-linecap="round"/>
    <circle r="6" fill="#ffc21a" stroke="CARD" stroke-width="2">
      <animateMotion dur="3.4s" repeatCount="indefinite"><mpath href="#mini"/></animateMotion>
    </circle>
    <rect x="36" y="186" width="54" height="9" rx="4.5" fill="LINE"/>
  </g>

  <!-- thẻ nhỏ: cột -->
  <g class="float-a">
    <g filter="url(#shadow)"><rect x="430" y="290" width="150" height="120" rx="24" fill="CARD"/></g>
    <rect class="bar" x="452" y="352" width="18" height="38" rx="7" fill="LINE"/>
    <rect class="bar b2" x="480" y="330" width="18" height="60" rx="7" fill="url(#gPurple)"/>
    <rect class="bar b3" x="508" y="314" width="18" height="76" rx="7" fill="url(#gGold)"/>
    <rect class="bar b4" x="536" y="336" width="18" height="54" rx="7" fill="#1a9e8f"/>
  </g>

  <!-- khiên -->
  <g class="float-b">
    <g filter="url(#shadow)">
      <path d="M470 40 l44 16 v32 c0 28 -20 46 -44 53 c-24 -7 -44 -25 -44 -53 v-32 z" fill="url(#gPurple)"/>
    </g>
    <path d="M452 90 l12 12 l23 -25" fill="none" stroke="#ffffff" stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>
  </g>

  <!-- đồng xu -->
  <g class="float-c">
    <g class="flip">
      <circle cx="92" cy="96" r="44" fill="url(#gGold)" filter="url(#shadow)"/>
      <circle cx="92" cy="96" r="32" fill="none" stroke="#fff3c4" stroke-width="4"/>
      <text x="92" y="111" text-anchor="middle" font-family="Montserrat, Arial, sans-serif" font-size="38"
            font-weight="800" fill="#ffffff">đ</text>
    </g>
  </g>
  <g class="float-a"><circle cx="118" cy="404" r="26" fill="url(#gPurple)" filter="url(#shadow)"/>
    <circle cx="118" cy="404" r="17" fill="none" stroke="#d9cdf5" stroke-width="3"/></g>

  <!-- lấp lánh -->
  <path class="twinkle" d="M560 190 l5 13 l13 5 l-13 5 l-5 13 l-5 -13 l-13 -5 l13 -5 z" fill="#ffc21a"/>
  <path class="twinkle tw2" d="M120 300 l4 10 l10 4 l-10 4 l-4 10 l-4 -10 l-10 -4 l10 -4 z" fill="#b9a2ff"/>
  <path class="twinkle tw3" d="M330 40 l4 10 l10 4 l-10 4 l-4 10 l-4 -10 l-10 -4 l10 -4 z" fill="#ffc21a"/>
</svg>
"""

_HERO_COLORS = {
    False: {"CARD": "#ffffff", "LINE2": "#f3eefc", "LINE": "#e9e2fa", "INNER": "#faf7ff"},
    True: {"CARD": "#221b3d", "LINE2": "#2c2450", "LINE": "#3a3163", "INNER": "#1b1630"},
}


def hero_art(dark: bool) -> str:
    svg = _HERO_SVG
    for placeholder, color in _HERO_COLORS[dark].items():
        svg = svg.replace(f'"{placeholder}"', f'"{color}"')
    return svg
