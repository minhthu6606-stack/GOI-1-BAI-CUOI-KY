"""
Phần "thiết kế" của giao diện: CSS bổ sung, dải giá chạy ngang (ticker) và hình minh họa trang chủ.

Màu chủ đạo: tím (#6d3fd9) và vàng (#f5b400) trên nền sáng. Màu cơ bản (nền, chữ, phông, bo góc) đặt
trong .streamlit/config.toml; file này chỉ thêm những gì config không làm được: thẻ nổi có bóng đổ,
khối hero có nền chuyển màu, dải giá chạy ngang, hiệu ứng khi rê chuột.

Thẻ nội dung được đánh dấu bằng `key` của st.container: key bắt đầu bằng "card" -> Streamlit gắn lớp CSS
"st-key-card..." -> CSS bên dưới tạo kiểu cho mọi thẻ như vậy. Hình minh họa là SVG tự vẽ (không dùng ảnh
có bản quyền của người khác).
"""
from __future__ import annotations

from html import escape

import streamlit as st

PURPLE, PURPLE_DARK, GOLD = "#6d3fd9", "#4b2aa6", "#f5b400"

CSS = """
<style>
/* ---------- thẻ nội dung ---------- */
[class*="st-key-card"] {
  background: #ffffff;
  border: 1px solid #ece6f8;
  border-radius: 20px;
  padding: 18px 20px 16px 20px;
  box-shadow: 0 4px 18px rgba(76, 42, 160, 0.07);
  transition: transform .18s ease, box-shadow .18s ease;
}
[class*="st-key-card"]:hover {
  transform: translateY(-3px);
  box-shadow: 0 12px 30px rgba(76, 42, 160, 0.14);
}
[class*="st-key-card"] [data-testid="stMetricValue"] { color: #1f1937; }

/* ---------- ô kết luận ---------- */
[class*="st-key-verdict"] {
  border-radius: 24px;
  padding: 24px 28px;
  border: 1px solid #e7defa;
  background: radial-gradient(circle at 95% 10%, rgba(245, 180, 0, .16), transparent 35%),
              linear-gradient(135deg, #f7f2ff 0%, #ffffff 70%);
  box-shadow: 0 6px 24px rgba(76, 42, 160, 0.08);
}
.st-key-verdict-danger  { border-left: 8px solid #dc2626 !important; }
.st-key-verdict-warning { border-left: 8px solid #e8860c !important; }
.st-key-verdict-good    { border-left: 8px solid #16a34a !important; }

/* ---------- khối hero trang chủ ---------- */
.st-key-hero {
  border-radius: 32px;
  padding: 40px 44px 34px 44px;
  border: 1px solid #ece4fb;
  background:
    radial-gradient(circle at 88% 18%, rgba(245, 180, 0, .28), transparent 38%),
    radial-gradient(circle at 8% 92%, rgba(109, 63, 217, .20), transparent 42%),
    linear-gradient(135deg, #f4edff 0%, #fffaf0 100%);
}
.hero-kicker { color: #6d3fd9; font-weight: 700; letter-spacing: .14em; font-size: .8rem; text-transform: uppercase; }
.hero-title { font-size: 3.1rem; font-weight: 800; line-height: 1.12; color: #1f1937; margin: .35rem 0 .8rem 0; }
.hero-title .glow {
  background: linear-gradient(90deg, #6d3fd9 0%, #b04fd6 45%, #f0a500 100%);
  -webkit-background-clip: text; background-clip: text; color: transparent;
}
.hero-sub { font-size: 1.08rem; color: #4a4560; line-height: 1.6; max-width: 34rem; }
.chips { margin-top: 1rem; }
.chip {
  display: inline-block; background: #ffffff; border: 1px solid #e3d8fb; border-radius: 999px;
  padding: 5px 14px; margin: 0 8px 8px 0; font-size: .86rem; color: #4b2aa6; font-weight: 600;
}
.chip b { color: #b98000; }
.ms {
  font-family: 'Material Symbols Rounded'; font-weight: normal; font-style: normal; font-size: 26px; line-height: 1;
  display: inline-block; white-space: nowrap; -webkit-font-feature-settings: 'liga'; font-feature-settings: 'liga';
}

/* ---------- thẻ tính năng và bước ---------- */
.feature-icon {
  width: 48px; height: 48px; border-radius: 16px; display: flex; align-items: center; justify-content: center;
  color: #ffffff; margin-bottom: .2rem; box-shadow: 0 6px 14px rgba(109, 63, 217, .25);
  background: linear-gradient(135deg, #7c4dff, #5a2fc2);
}
.feature-icon.gold { background: linear-gradient(135deg, #f7c534, #e09b00); box-shadow: 0 6px 14px rgba(224, 155, 0, .28); }
.step-no {
  width: 34px; height: 34px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center;
  background: #f5b400; color: #2b2100; font-weight: 800; margin-right: .5rem;
}
.section-title { font-size: 1.6rem; font-weight: 800; color: #1f1937; margin: 1.6rem 0 .2rem 0; }
.section-title .glow { color: #6d3fd9; }

/* ---------- dải giá chạy ngang ---------- */
.ticker {
  overflow: hidden; white-space: nowrap; border-radius: 16px; border: 1px solid #ece6f8;
  background: #ffffff; box-shadow: 0 2px 10px rgba(76, 42, 160, .06); padding: 9px 0; margin-bottom: .4rem;
  -webkit-mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent);
          mask-image: linear-gradient(90deg, transparent, #000 4%, #000 96%, transparent);
}
.ticker-track { display: inline-flex; gap: 34px; padding-left: 34px; animation: ticker 45s linear infinite; }
.ticker:hover .ticker-track { animation-play-state: paused; }
@keyframes ticker { from { transform: translateX(0); } to { transform: translateX(-50%); } }
.tick { font-size: .92rem; color: #1f1937; }
.tick b { margin-right: 6px; }
.tick .tag { border-radius: 6px; padding: 1px 7px; margin-left: 6px; font-weight: 700; font-size: .82rem; }
.tick .up { background: #dcfce7; color: #15803d; }
.tick .down { background: #fee2e2; color: #b91c1c; }
.tick .flat { background: #fef3c7; color: #92400e; }
.tick-label { font-size: .8rem; color: #6d3fd9; font-weight: 700; letter-spacing: .06em; }

/* ---------- thanh bên ---------- */
[data-testid="stSidebar"] { border-right: 1px solid #ece6f8; }
[data-testid="stSidebarNav"] a[aria-current="page"] {
  background: linear-gradient(90deg, #6d3fd9, #8a5cf0) !important; border-radius: 12px;
}
[data-testid="stSidebarNav"] a[aria-current="page"] span { color: #ffffff !important; }
[data-testid="stSidebarNav"] a:hover { border-radius: 12px; }

/* ---------- chi tiết nhỏ ---------- */
h1 { letter-spacing: -0.02em; }
[data-testid="stPageLink"] a { border-radius: 12px; }
</style>
"""


def inject_css() -> None:
    st.html(CSS)


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


# ---------------------------------------------------------------- hình minh họa trang chủ (SVG tự vẽ)

HERO_ART = """<svg viewBox="0 0 520 400" xmlns="http://www.w3.org/2000/svg" role="img"
     aria-label="Minh họa: thẻ sức khỏe danh mục với biểu đồ vành khuyên, đường nhịp tim và đồng xu">
  <style>
    .float-a { animation: floaty 6s ease-in-out infinite; }
    .float-b { animation: floaty 7s ease-in-out infinite reverse; }
    .float-c { animation: floaty 5s ease-in-out infinite; animation-delay: -2s; }
    @keyframes floaty { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
    .pulse-line { stroke-dasharray: 420; stroke-dashoffset: 420; animation: draw 3.2s ease-out forwards; }
    @keyframes draw { to { stroke-dashoffset: 0; } }
  </style>
  <defs>
    <linearGradient id="gPurple" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#8a5cf0"/><stop offset="1" stop-color="#5a2fc2"/>
    </linearGradient>
    <linearGradient id="gGold" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#ffd75e"/><stop offset="1" stop-color="#e09b00"/>
    </linearGradient>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="150%">
      <feDropShadow dx="0" dy="10" stdDeviation="12" flood-color="#4b2aa6" flood-opacity="0.16"/>
    </filter>
  </defs>

  <!-- quầng sáng nền -->
  <circle cx="380" cy="90" r="90" fill="#f5b400" opacity="0.14"/>
  <circle cx="140" cy="300" r="80" fill="#6d3fd9" opacity="0.10"/>

  <!-- thẻ chính: sức khỏe danh mục -->
  <g filter="url(#shadow)">
    <rect x="120" y="70" width="290" height="250" rx="28" fill="#ffffff"/>
  </g>
  <rect x="146" y="96" width="120" height="12" rx="6" fill="#ece6f8"/>
  <rect x="146" y="116" width="80" height="10" rx="5" fill="#f3effb"/>
  <!-- biểu đồ vành khuyên -->
  <g transform="translate(205 205) rotate(-90)">
    <circle r="54" fill="none" stroke="#f1ecfb" stroke-width="20"/>
    <circle r="54" fill="none" stroke="url(#gPurple)" stroke-width="20" stroke-dasharray="153 340" stroke-linecap="round"/>
    <circle r="54" fill="none" stroke="url(#gGold)" stroke-width="20" stroke-dasharray="85 340"
            stroke-dashoffset="-160" stroke-linecap="round"/>
    <circle r="54" fill="none" stroke="#1a9e8f" stroke-width="20" stroke-dasharray="55 340"
            stroke-dashoffset="-252" stroke-linecap="round"/>
  </g>
  <circle cx="205" cy="205" r="30" fill="#faf7ff"/>
  <path d="M195 205 l7 7 l14 -15" fill="none" stroke="#16a34a" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
  <!-- các dòng chỉ số -->
  <rect x="290" y="160" width="96" height="10" rx="5" fill="#ece6f8"/>
  <rect x="290" y="178" width="66" height="10" rx="5" fill="#f5b400" opacity="0.8"/>
  <rect x="290" y="206" width="96" height="10" rx="5" fill="#ece6f8"/>
  <rect x="290" y="224" width="52" height="10" rx="5" fill="#6d3fd9" opacity="0.8"/>
  <!-- đường nhịp tim -->
  <polyline class="pulse-line" points="140,292 200,292 218,268 238,314 258,276 272,292 392,292"
            fill="none" stroke="#6d3fd9" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>

  <!-- thẻ nhỏ: cột -->
  <g class="float-a">
    <g filter="url(#shadow)"><rect x="372" y="236" width="128" height="104" rx="22" fill="#ffffff"/></g>
    <rect x="392" y="296" width="16" height="26" rx="6" fill="#d9cdf5"/>
    <rect x="416" y="278" width="16" height="44" rx="6" fill="url(#gPurple)"/>
    <rect x="440" y="264" width="16" height="58" rx="6" fill="url(#gGold)"/>
    <rect x="464" y="284" width="16" height="38" rx="6" fill="#1a9e8f"/>
  </g>

  <!-- khiên kiểm tra -->
  <g class="float-b">
    <g filter="url(#shadow)">
      <path d="M392 52 l38 14 v28 c0 24 -18 40 -38 46 c-20 -6 -38 -22 -38 -46 v-28 z" fill="url(#gPurple)"/>
    </g>
    <path d="M377 96 l11 11 l20 -22" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>
  </g>

  <!-- đồng xu -->
  <g class="float-c">
    <ellipse cx="78" cy="148" rx="40" ry="40" fill="url(#gGold)" filter="url(#shadow)"/>
    <ellipse cx="78" cy="148" rx="29" ry="29" fill="none" stroke="#fff3c4" stroke-width="4"/>
    <text x="78" y="161" text-anchor="middle" font-family="Be Vietnam Pro, Arial, sans-serif" font-size="34"
          font-weight="800" fill="#ffffff">đ</text>
  </g>
  <g class="float-a">
    <ellipse cx="96" cy="250" rx="24" ry="24" fill="url(#gPurple)" filter="url(#shadow)"/>
    <ellipse cx="96" cy="250" rx="16" ry="16" fill="none" stroke="#d9cdf5" stroke-width="3"/>
  </g>
</svg>
"""
