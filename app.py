# -*- coding: utf-8 -*-
"""
Aplikasi Manajemen Stok Masuk Keluar & Laporan Laba Rugi — Toko Grosir
Stack : Streamlit + SQLite/PostgreSQL(Supabase) + Pandas
DB    : otomatis pakai Supabase jika ada secret SUPABASE_DB_URL,
        fallback ke SQLite lokal (grosir.db) jika tidak ada.
Tema  : Liquid Glass
Run   : streamlit run app.py
"""

import io
import sqlite3
from datetime import date, datetime

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Aplikasi Toko Grosir",
    page_icon="🏬",
    layout="wide",
)

DB_PATH = "grosir.db"

# ============================================================
#  DATABASE (SQLite lokal otomatis, atau Supabase jika dikonfigurasi)
# ============================================================


def _detect_db_url():
    try:
        url = st.secrets.get("SUPABASE_DB_URL", "")
        if url:
            return str(url).strip()
    except Exception:
        pass
    return ""

DB_URL = _detect_db_url()
IS_PG = bool(DB_URL)

if IS_PG:
    import psycopg2

    if "sslmode" not in DB_URL:
        DB_URL += ("&" if "?" in DB_URL else "?") + "sslmode=require"


def get_sqlite_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    if IS_PG:
        ddl_barang = """
            CREATE TABLE IF NOT EXISTS barang (
                sku         TEXT PRIMARY KEY,
                nama        TEXT NOT NULL,
                kategori    TEXT,
                harga_beli  DOUBLE PRECISION NOT NULL DEFAULT 0,
                harga_jual  DOUBLE PRECISION NOT NULL DEFAULT 0,
                stok        INTEGER NOT NULL DEFAULT 0,
                limit_alert INTEGER NOT NULL DEFAULT 10
            )
        """
        ddl_masuk = """
            CREATE TABLE IF NOT EXISTS barang_masuk (
                id       BIGSERIAL PRIMARY KEY,
                sku      TEXT NOT NULL,
                jumlah   INTEGER NOT NULL,
                catatan  TEXT,
                tanggal  TEXT NOT NULL
            )
        """
        ddl_keluar = """
            CREATE TABLE IF NOT EXISTS barang_keluar (
                id            BIGSERIAL PRIMARY KEY,
                sku           TEXT NOT NULL,
                jumlah        INTEGER NOT NULL,
                harga_beli    DOUBLE PRECISION NOT NULL,
                harga_jual    DOUBLE PRECISION NOT NULL,
                omzet         DOUBLE PRECISION NOT NULL,
                laba          DOUBLE PRECISION NOT NULL,
                pelanggan     TEXT,
                tanggal       TEXT NOT NULL
            )
        """
        ddl_biaya = """
            CREATE TABLE IF NOT EXISTS biaya_operasional (
                id         BIGSERIAL PRIMARY KEY,
                keterangan TEXT NOT NULL,
                jumlah     DOUBLE PRECISION NOT NULL,
                tanggal    TEXT NOT NULL
            )
        """
        for ddl in (ddl_barang, ddl_masuk, ddl_keluar, ddl_biaya):
            conn = psycopg2.connect(DB_URL)
            conn.cursor().execute(ddl)
            conn.commit()
            conn.close()
        return

    conn = get_sqlite_conn()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS barang (
            sku         TEXT PRIMARY KEY,
            nama        TEXT NOT NULL,
            kategori    TEXT,
            harga_beli  REAL NOT NULL DEFAULT 0,
            harga_jual  REAL NOT NULL DEFAULT 0,
            stok        INTEGER NOT NULL DEFAULT 0,
            limit_alert INTEGER NOT NULL DEFAULT 10
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS barang_masuk (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            sku      TEXT NOT NULL,
            jumlah   INTEGER NOT NULL,
            catatan  TEXT,
            tanggal  TEXT NOT NULL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS barang_keluar (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            sku           TEXT NOT NULL,
            jumlah        INTEGER NOT NULL,
            harga_beli    REAL NOT NULL,
            harga_jual    REAL NOT NULL,
            omzet         REAL NOT NULL,
            laba          REAL NOT NULL,
            pelanggan     TEXT,
            tanggal       TEXT NOT NULL
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS biaya_operasional (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            keterangan TEXT NOT NULL,
            jumlah     REAL NOT NULL,
            tanggal    TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


DB_CONFIG_ERROR = None
try:
    init_db()
except Exception as _e:
    if IS_PG:
        DB_CONFIG_ERROR = _e
    else:
        raise


def df(sql, params=()):
    """Jalankan SELECT dan kembalikan DataFrame."""
    if IS_PG:
        conn = psycopg2.connect(DB_URL)
        try:
            out = pd.read_sql_query(sql.replace("?", "%s"), conn, params=params)
        finally:
            conn.close()
        return out
    conn = get_sqlite_conn()
    out = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return out


def run(sql, params=()):
    """Jalankan INSERT/UPDATE/DELETE."""
    if IS_PG:
        conn = psycopg2.connect(DB_URL)
        conn.cursor().execute(sql.replace("?", "%s"), params)
        conn.commit()
        conn.close()
        return
    conn = get_sqlite_conn()
    conn.execute(sql, params)
    conn.commit()
    conn.close()


def rupiah(v):
    return f"Rp {v:,.0f}".replace(",", ".")


# ============================================================
#  DESAIN & KOMPONEN VISUAL — TEMA LIQUID GLASS
# ============================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

/* ===== DASAR & LATAR LIQUID ===== */
.stApp{
  font-family:'Inter','Segoe UI',sans-serif;
  background:transparent;
  color:#1e293b;
}
.stApp::before{
  content:"";position:fixed;inset:0;z-index:-2;
  background:
    radial-gradient(720px 480px at 90% -8%, rgba(79,70,229,.11), transparent 62%),
    radial-gradient(560px 420px at -10% 8%, rgba(14,165,233,.10), transparent 58%),
    radial-gradient(760px 520px at 55% 115%, rgba(16,185,129,.08), transparent 60%),
    linear-gradient(180deg,#f7f9fc 0%,#eef2f8 100%);
}
.stApp::after{
  content:"";position:fixed;z-index:-1;width:44vmax;height:44vmax;
  border-radius:46% 54% 58% 42%/54% 46% 54% 46%;
  left:-16vmax;top:-14vmax;
  background:radial-gradient(circle at 35% 35%, rgba(99,102,241,.07), transparent 65%);
  filter:blur(6px);
  animation:drift 34s ease-in-out infinite alternate;
}
@keyframes drift{
  0%{transform:translate(0,0) rotate(0deg);}
  50%{transform:translate(6vmax,4vmax) rotate(14deg);}
  100%{transform:translate(2vmax,9vmax) rotate(-10deg);}
}
#MainMenu,footer,header{visibility:hidden;}
a:link,a:visited{color:#4f46e5;}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"]{
  background:rgba(251,252,255,.72) !important;
  backdrop-filter:blur(26px) saturate(160%);-webkit-backdrop-filter:blur(26px) saturate(160%);
  border-right:1px solid rgba(255,255,255,.7);
}
section[data-testid="stSidebar"] *{color:#334155 !important;}
.brand{display:flex;gap:12px;align-items:center;margin:6px 0 18px;}
.brand-ico{font-size:1.5rem;width:50px;height:50px;display:flex;align-items:center;justify-content:center;border-radius:16px;
  background:linear-gradient(135deg,rgba(79,70,229,.95),rgba(109,40,217,.95));
  box-shadow:0 10px 24px -8px rgba(79,70,229,.55), inset 0 1px 1px rgba(255,255,255,.35);}
.brand h1{font-size:1.02rem;font-weight:800;color:#0f172a !important;margin:0 !important;letter-spacing:-.2px;line-height:1.2;}
.brand p{font-size:.7rem;color:#64748b !important;margin:2px 0 0 !important;font-weight:500;}
.menulabel{font-size:.62rem;font-weight:800;letter-spacing:1.6px;text-transform:uppercase;color:#94a3b8 !important;margin-bottom:8px;}
section[data-testid="stSidebar"] .stRadio [role=radiogroup]{gap:5px;}
section[data-testid="stSidebar"] .stRadio label{
  background:rgba(255,255,255,.55);border:1px solid rgba(15,23,42,.06);
  border-radius:13px;padding:10px 13px;font-weight:600;font-size:.86rem;color:#334155 !important;
  transition:all .18s ease;min-height:0 !important;
  box-shadow:0 1px 2px rgba(16,24,40,.03);
}
section[data-testid="stSidebar"] .stRadio label:hover{background:#fff;transform:translateX(3px);box-shadow:0 4px 12px rgba(16,24,40,.08);}
section[data-testid="stSidebar"] .stRadio label:has(input:checked){
  background:linear-gradient(135deg,#4f46e5,#7c3aed);border-color:transparent;
  box-shadow:0 10px 22px -8px rgba(79,70,229,.55);
}
section[data-testid="stSidebar"] .stRadio label:has(input:checked) *{color:#fff !important;}
section[data-testid="stSidebar"] .stRadio [role=radiogroup] input{position:absolute;opacity:0;pointer-events:none;}
.sidechip{background:rgba(15,23,42,.04);border:1px solid rgba(15,23,42,.07);border-radius:11px;padding:8px 12px;font-size:.76rem;font-weight:500;color:#475569 !important;margin-top:6px;}
section[data-testid="stSidebar"] .stButton>button{
  background:rgba(15,23,42,.05) !important;border:1px solid rgba(15,23,42,.1) !important;color:#334155 !important;
}

/* ===== JUDUL & SEKSI ===== */
.ptitle h1{font-size:1.65rem;font-weight:800;color:#0f172a;margin:0;letter-spacing:-.5px;}
.ptitle p{color:#64748b;font-size:.86rem;margin:4px 0 10px;font-weight:500;}
.sechead{display:flex;align-items:baseline;gap:8px;font-size:1rem;font-weight:800;color:#0f172a;margin:22px 0 10px;letter-spacing:-.2px;}
.sechead small{font-weight:600;color:#94a3b8;font-size:.75rem;margin-left:2px;}

/* ===== KARTU KPI (LIQUID GLASS) ===== */
.kpi-card{border-radius:20px;padding:17px 18px;color:#0f172a;position:relative;overflow:hidden;
  background:rgba(255,255,255,.66);
  backdrop-filter:blur(18px) saturate(150%);-webkit-backdrop-filter:blur(18px) saturate(150%);
  border:1px solid rgba(255,255,255,.7);
  box-shadow:0 1px 2px rgba(16,24,40,.05),0 16px 38px -20px rgba(16,24,40,.20);}
.kpi-glow{position:absolute;right:-36px;bottom:-36px;width:128px;height:128px;border-radius:50%;
  background:radial-gradient(circle at 42% 42%, var(--acg), transparent 68%);opacity:.5;filter:blur(2px);}
.kpi-ico{width:44px;height:44px;display:flex;align-items:center;justify-content:center;border-radius:13px;margin-bottom:12px;
  color:var(--ac);background:var(--acb);
  box-shadow:inset 0 0 0 1px var(--acb2);}
.kpi-ico svg{display:block;}
.kpi-label{font-size:.68rem;font-weight:700;color:#64748b;letter-spacing:.7px;text-transform:uppercase;}
.kpi-val{font-size:1.42rem;font-weight:800;margin-top:3px;letter-spacing:-.6px;position:relative;z-index:1;}
.kpi-sub{font-size:.73rem;font-weight:600;margin-top:7px;color:#64748b;}

/* ===== MINI STAT ===== */
.mstat{background:rgba(255,255,255,.66);backdrop-filter:blur(14px) saturate(150%);-webkit-backdrop-filter:blur(14px) saturate(150%);
  border:1px solid rgba(255,255,255,.7);border-radius:15px;padding:12px 15px;
  box-shadow:0 1px 2px rgba(16,24,40,.04),0 10px 26px -14px rgba(16,24,40,.14);position:relative;}
.mstat::before{content:"";position:absolute;left:0;top:11px;bottom:11px;width:3px;border-radius:3px;background:var(--ac,#4f46e5);}
.mstat-l{font-size:.68rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.6px;padding-left:9px;}
.mstat-v{font-size:.98rem;font-weight:800;color:#0f172a;margin-top:3px;padding-left:9px;letter-spacing:-.3px;}

/* ===== TOMBOL ===== */
div.stButton>button,div.stFormSubmitButton>button,div.stDownloadButton>button{
  border-radius:12px;font-weight:600;transition:all .18s ease;
  background:rgba(255,255,255,.6);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);
  border:1px solid rgba(15,23,42,.09) !important;color:#334155 !important;
  box-shadow:0 1px 2px rgba(16,24,40,.05);
}
div.stButton>button:hover,div.stFormSubmitButton>button:hover,div.stDownloadButton>button:hover{
  transform:translateY(-2px);background:#fff;box-shadow:0 10px 24px -10px rgba(16,24,40,.22);
}
div.stButton>button[kind="primary"],div.stFormSubmitButton>button[kind="primary"],div.stDownloadButton>button[kind="primary"]{
  background:linear-gradient(135deg,#4f46e5,#7c3aed) !important;color:#fff !important;border:none !important;
  box-shadow:0 10px 22px -8px rgba(79,70,229,.5);
}

/* ===== TABEL & EXPANDER ===== */
div[data-testid="stDataFrame"],div[data-testid="stTable"]{border-radius:16px;overflow:hidden;
  background:rgba(255,255,255,.6);
  border:1px solid rgba(255,255,255,.7);}
div[data-testid="stExpander"]{background:rgba(255,255,255,.6);backdrop-filter:blur(14px);
  border-radius:16px;border:1px solid rgba(255,255,255,.7) !important;
  box-shadow:0 10px 30px -18px rgba(16,24,40,.14);}

/* ===== STATEMEN LABA RUGI ===== */
.plcard{background:rgba(255,255,255,.7);backdrop-filter:blur(18px) saturate(150%);-webkit-backdrop-filter:blur(18px) saturate(150%);
  border:1px solid rgba(255,255,255,.75);border-radius:20px;padding:6px 22px;
  box-shadow:0 16px 40px -20px rgba(16,24,40,.18);max-width:760px;}
.plrow{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px dashed rgba(15,23,42,.12);font-size:.94rem;color:#334155;}
.plrow .plval{font-weight:800;color:#0f172a;}
.plrow.minus .plval{color:#dc2626;}
.plrow.total{border-bottom:none;background:linear-gradient(90deg,rgba(5,150,105,.10),rgba(5,150,105,.02));margin:6px -22px 0;padding:16px 22px;border-radius:0 0 20px 20px;font-weight:800;color:#065f46;}
.plrow.total .plval{color:#047857;font-size:1.2rem;}

/* ===== KOSONG & PROGRESS ===== */
.empty{background:rgba(255,255,255,.55);border:1.5px dashed rgba(15,23,42,.14);color:#64748b;text-align:center;border-radius:16px;padding:26px;font-weight:600;backdrop-filter:blur(10px);}
div.stProgress>div>div{background:linear-gradient(90deg,#f59e0b,#ef4444);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


# -- Ikon SVG minimalis (garis, bukan emoji) --
_S = '<svg width="21" height="21" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">'
ICON = {
    "cash": _S + '<rect x="2" y="6" width="20" height="13" rx="2.5"/><circle cx="12" cy="12.5" r="2.4"/><path d="M6.5 6V5.2A2.2 2.2 0 0 1 8.7 3h6.6a2.2 2.2 0 0 1 2.2 2.2V6"/></svg>',
    "box": _S + '<path d="M21 8.2 12 3 3 8.2v7.6L12 21l9-5.2V8.2z"/><path d="M3.4 8.4 12 13.3l8.6-4.9"/><path d="M12 13.3V21"/></svg>',
    "chart": _S + '<path d="M3 17.5 9.5 11l4 4L21 7"/><path d="M15.5 7H21v5.5"/></svg>',
    "tag": _S + '<path d="M12.6 2.6 21 11a2.2 2.2 0 0 1 0 3.1L14 21.1a2.2 2.2 0 0 1-3.1 0L2.5 12.6V4.6a2 2 0 0 1 2-2z"/><circle cx="7.3" cy="7.3" r="1.3"/></svg>',
    "receipt": _S + '<path d="M6 2.5h12v19l-2-1.4-2 1.4-2-1.4-2 1.4-2-1.4-2 1.4z"/><path d="M9 7h6"/><path d="M9 10.5h6"/><path d="M9 14h4"/></svg>',
    "wallet": _S + '<rect x="2.5" y="5.5" width="19" height="14" rx="3"/><path d="M17 12.5h2"/><path d="M15.5 5.5V4a2 2 0 0 0-2-2H6a3 3 0 0 0-3 3.5"/></svg>',
    "coin": _S + '<circle cx="12" cy="12" r="9"/><path d="M12 7v10"/><path d="M15 9.5c0-1.4-1.3-2.5-3-2.5s-3 1-3 2.4c0 3.2 6 1.8 6 5 0 1.4-1.3 2.4-3 2.4s-3-1.1-3-2.5"/></svg>',
}


def tint(hexc, alpha):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def page_title(emoji, text, caption_text):
    st.markdown(f'<div class="ptitle"><h1>{emoji} {text}</h1><p>{caption_text}</p></div>', unsafe_allow_html=True)


def section(emoji, text, note=""):
    small = f"<small>{note}</small>" if note else ""
    st.markdown(f'<div class="sechead">{emoji}&nbsp; {text}&nbsp;&nbsp;{small}</div>', unsafe_allow_html=True)


def kpi_card(label, value, icon_key, accent, sub=""):
    svg = ICON.get(icon_key, "")
    st.markdown(
        f"""<div class="kpi-card" style="--ac:{accent};--acb:{tint(accent,.10)};--acb2:{tint(accent,.24)};--acg:{tint(accent,.30)};">
        <div class="kpi-glow"></div>
        <div class="kpi-ico">{svg}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-val">{value}</div>
        <div class="kpi-sub">{sub}</div></div>""",
        unsafe_allow_html=True,
    )


def mini_stat(label, value, color="#4f46e5"):
    st.markdown(
        f'<div class="mstat" style="--ac:{color};"><div class="mstat-l">{label}</div><div class="mstat-v">{value}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(text, icon="📭"):
    st.markdown(f'<div class="empty">{icon}&nbsp; {text}</div>', unsafe_allow_html=True)


def goto(label_menu):
    """Navigasi programatik: simpan target, rerun dulu, baru ubah widget radio."""
    st.session_state["__nav_target"] = label_menu
    st.rerun()


# Terapkan target navigasi SEBELUM widget radio dibuat
if "__nav_target" in st.session_state:
    st.session_state["Navigasi"] = st.session_state.pop("__nav_target")


# ============================================================
#  HALAMAN DIAGNOSA — jika Supabase gagal terhubung
# ============================================================
def _mask_url(url):
    import re

    return re.sub(r"://([^:/@]+):([^@]+)@", r"://\1:******@", url)


if DB_CONFIG_ERROR:
    import urllib.parse as _up

    err_txt = str(DB_CONFIG_ERROR)
    low = err_txt.lower()

    st.markdown('<div class="ptitle"><h1>🔌 Koneksi Supabase Gagal</h1><p>Aplikasi mendeteksi SUPABASE_DB_URL, tapi tidak bisa menyambung ke database-nya.</p></div>', unsafe_allow_html=True)
    st.error(f"**Detail teknis:** `{err_txt}`")

    tips = []

    # deteksi placeholder yang belum diganti
    try:
        _parsed = _up.urlsplit(DB_URL)
        _pwd = _parsed.password or ""
    except Exception:
        _parsed, _pwd = None, ""
    if (not _pwd) or "password" in _pwd.lower() or "your-" in _pwd.lower():
        tips.append(
            ("Password masih placeholder / kosong",
             "Buka bagian `[YOUR-PASSWORD]` di secret — itu harus diganti dengan "
             "password database asli yang kamu buat di Supabase. Contoh benar:")
        )

    if "password authentication failed" in low or ("password" in low and "auth" in low):
        tips.append(
            ("Password database salah",
             "Password yang diketik tidak cocok. Buka pop-up **Connect → Connection string** di "
             "Supabase, klik **Reset database password**, buat password baru (huruf+angka saja), "
             "lalu perbarui secret dengan password barunya.")
        )
    if "could not translate host name" in low or "not known" in low:
        tips.append(
            ("Hostname salah",
             "Cek bagian host pada URL — pastikan menyamai `aws-1-eu-west-3.pooler.supabase.com` "
             "dengan angka project-mu, tanpa salah ketik.")
        )
    if "connection refused" in low or "timed out" in low or "timeout" in low:
        tips.append(
            ("Port/servis bermasalah",
             "Pastikan memakai **Transaction pooler** (port `6543`), bukan session pooler "
             "(`5432`) atau direct connection. Cek juga project Supabase tidak sedang PAUSED.")
        )
    if "invalid" in low and ("connection" in low or "uri" in low or "syntax" in low):
        tips.append(
            ("Format URL salah",
             "Biasanya karena password mengandung karakter spesial (`@ / : #`). "
             "Reset password menjadi huruf+angka saja.")
        )
    if "ssl" in low:
        tips.append(
            ("SSL",
             "Terguae koneksi butuh SSL — kode sudah menambahkan `sslmode=require` otomatis; "
             "pastikan URL tidak diubah manual.")
        )
    if not tips:
        tips.append(
            ("Penyebab umum lainnya",
             "Cek kembali format secret di Streamlit Cloud → Settings → Secrets, "
             "lalu bandingkan dengan format dari Supabase Connect → Connection pooling → Transaction mode.")
        )

    st.markdown('<div class="sechead">🔍 Kemungkinan penyebab &amp; solusi</div>', unsafe_allow_html=True)
    for i, (judul, cara) in enumerate(tips, 1):
        with st.container(border=True):
            st.markdown(f"**{i}. {judul}**")
            st.markdown(cara)

    st.markdown('<div class="sechead">🧾 Koneksi yang sedang terbaca dari secret</div>', unsafe_allow_html=True)
    st.code(
        f"host : {_parsed.hostname if _parsed else '?'}\n"
        f"port : {_parsed.port if _parsed else '?'}\n"
        f"user : {_parsed.username if _parsed else '?'}\n"
        f"sdnl : {'ADA' if _pwd else 'TIDAK ADA'}\n\n"
        f"URL (password disensor): {_mask_url(DB_URL)}",
        language="text",
    )

    st.info("💡 **Cara perbaiki:** Streamlit Cloud → aplikasi Toko Grosir → ⋮ → "
            "**Settings → Secrets** → perbaiki nilai `SUPABASE_DB_URL` → Save. "
            "Aplikasi ini otomatis me-reload setelah secret diubah.")
    st.stop()


# ============================================================
#  SIDEBAR NAVIGASI
# ============================================================

def sidebar():
    st.sidebar.markdown(
        '<div class="brand"><div class="brand-ico">🏬</div><div><h1>Toko Grosir</h1>'
        "<p>Manajemen Stok &amp; Laba Rugi</p></div></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown('<div class="menulabel">📋 Navigasi Menu</div>', unsafe_allow_html=True)

    menu = st.sidebar.radio(
        "Navigasi",
        [
            "📊 Dashboard",
            "📥 Barang Masuk / Restock",
            "📤 Barang Keluar / POS Kasir",
            "📈 Laporan Laba Rugi (P&L)",
        ],
        key="Navigasi",
        label_visibility="collapsed",
    )
    st.sidebar.markdown('<div class="menulabel">ℹ️ Info</div>', unsafe_allow_html=True)
    db_label = "☁️ Supabase — data aman" if IS_PG else "💾 SQLite — data lokal"
    st.sidebar.markdown(f'<div class="sidechip">{db_label}</div>', unsafe_allow_html=True)
    st.sidebar.markdown(
        f'<div class="sidechip">📅 {datetime.now().strftime("%A, %d %B %Y")}</div>',
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.rerun()
    return menu


menu = sidebar()

# ============================================================
#  1) DASHBOARD
# ============================================================
if menu.startswith("📊"):

    page_title("Dashboard", "Toko Grosir", "Ringkasan performa bisnis secara real-time")

    # -- Tombol aksi cepat --
    qa = st.columns(4)
    if qa[0].button("🛒 Transaksi Baru", use_container_width=True):
        goto("📤 Barang Keluar / POS Kasir")
    if qa[1].button("📥 Restock Barang", use_container_width=True):
        goto("📥 Barang Masuk / Restock")
    if qa[2].button("📈 Lihat Laba Rugi", use_container_width=True):
        goto("📈 Laporan Laba Rugi (P&L)")
    if qa[3].button("🔄 Refresh", use_container_width=True):
        st.rerun()

    section("💰", "Performa Keuangan", "Periode berjalan (sejak awal)")

    omzet = df("SELECT COALESCE(SUM(omzet),0)  AS t FROM barang_keluar").iloc[0]["t"]
    hpp = df(
        "SELECT COALESCE(SUM(harga_beli * jumlah),0) AS t FROM barang_keluar"
    ).iloc[0]["t"]
    biaya = df("SELECT COALESCE(SUM(jumlah),0) AS t FROM biaya_operasional").iloc[0]["t"]
    laba_bersih = omzet - hpp - biaya
    jml_sku = df("SELECT COUNT(*) AS t FROM barang").iloc[0]["t"]
    nilai_stok = df("SELECT COALESCE(SUM(harga_beli * stok),0) AS t FROM barang").iloc[0]["t"]
    margin = 0 if omzet == 0 else laba_bersih / omzet * 100

    r1 = st.columns(4)
    with r1[0]:
        kpi_card("Total Omzet", rupiah(omzet), "cash", "#4F46E5")
    with r1[1]:
        kpi_card("Total HPP / Modal", rupiah(hpp), "box", "#D97706")
    with r1[2]:
        kpi_card("Laba Bersih", rupiah(laba_bersih), "chart", "#059669", f"Margin {margin:.1f}%")
    with r1[3]:
        kpi_card("Jumlah SKU", f"{int(jml_sku)} item", "tag", "#7C3AED")

    r2 = st.columns(2)
    with r2[0]:
        mini_stat("Nilai Persediaan (Modal)", rupiah(nilai_stok), "#6366f1")
    with r2[1]:
        mini_stat("Total Biaya Operasional", rupiah(biaya), "#ef4444")
    st.caption("💡 Laba bersih = Omzet − HPP − Biaya Operasional")

    # -- Peringatan stok menipis --
    section("⚠️", "Peringatan Stok Menipis", "Barang dengan stok di bawah limit")
    rendah = df(
        "SELECT sku, nama, kategori, stok, limit_alert, harga_jual FROM barang WHERE stok <= limit_alert ORDER BY stok ASC"
    )
    if rendah.empty:
        empty_state("Semua stok barang aman, tidak ada yang menipis.", "✅")
    else:
        st.error(f"🚨 Ada {len(rendah)} SKU yang perlu segera direstock!")
        for _, r in rendah.iterrows():
            p = 100 if r["limit_alert"] <= 0 else min(100, max(4, int(r["stok"] / max(r["limit_alert"], 1) * 100)))
            with st.container(border=True):
                st.markdown(
                    f"**{r['sku']}** — {r['nama']}  \n"
                    f"Stok: **{int(r['stok'])}** (Limit alert: {int(r['limit_alert'])}) · "
                    f"Harga jual: {rupiah(r['harga_jual'])}"
                )
                st.progress(p, text=f"Stok {int(r['stok'])} / {int(r['limit_alert'])}")

    # -- Transaksi terbaru --
    section("🧾", "Transaksi Terbaru", "8 penjualan terakhir")
    terbaru = df(
        "SELECT tanggal, sku, jumlah, harga_jual, omzet, laba, pelanggan FROM barang_keluar ORDER BY id DESC LIMIT 8"
    )
    if terbaru.empty:
        empty_state("Belum ada transaksi penjualan — yuk mulai jualan!", "🛒")
    else:
        tampil = terbaru.rename(
            columns={
                "tanggal": "Tanggal", "sku": "SKU", "jumlah": "Qty",
                "harga_jual": "H. Jual", "omzet": "Omzet", "laba": "Laba",
                "pelanggan": "Pelanggan",
            }
        )
        tampil["H. Jual"] = tampil["H. Jual"].map(rupiah)
        tampil["Omzet"] = tampil["Omzet"].map(rupiah)
        tampil["Laba"] = tampil["Laba"].map(rupiah)
        st.table(tampil)


# ============================================================
#  2) BARANG MASUK / RESTOCK
# ============================================================
elif menu.startswith("📥"):

    page_title("Barang Masuk / Restock", "Toko Grosir", "Kelola master barang & catat penerimaan stok grosir")

    section("➕", "Tambah Master Barang Baru")
    with st.form("form_master", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        sku = col_a.text_input("Kode SKU (unik)", placeholder="mis. BRT-001")
        nama = col_b.text_input("Nama Barang", placeholder="mis. Beras Premium 25kg")
        col_c, col_d, col_e = st.columns(3)
        kategori = col_c.text_input("Kategori Grosir", placeholder="mis. Sembako")
        harga_beli = col_d.number_input("Harga Beli /unit (Rp)", min_value=0, step=500)
        harga_jual = col_e.number_input("Harga Jual Grosir /unit (Rp)", min_value=0, step=500)
        col_f, col_g = st.columns(2)
        stok_awal = col_f.number_input("Stok Masuk (unit awal)", min_value=0, step=1)
        limit_alert = col_g.number_input("Limit Alert Stok Menipis", min_value=0, step=1, value=10)
        simpan = st.form_submit_button("💾 Simpan Master Barang", type="primary", use_container_width=True)

    if simpan:
        if not sku.strip() or not nama.strip():
            st.error("❌ Kode SKU dan Nama Barang wajib diisi!")
        else:
            try:
                run(
                    "INSERT INTO barang (sku, nama, kategori, harga_beli, harga_jual, stok, limit_alert) VALUES (?,?,?,?,?,?,?)",
                    (sku.strip(), nama.strip(), kategori.strip(), harga_beli, harga_jual, stok_awal, limit_alert),
                )
                if stok_awal > 0:
                    run(
                        "INSERT INTO barang_masuk (sku, jumlah, catatan, tanggal) VALUES (?,?,?,?)",
                        (sku.strip(), stok_awal, "Stok awal master barang", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                    )
                st.session_state["toast_ok"] = f"✅ SKU {sku} tersimpan di master barang!"
                st.rerun()
            except sqlite3.IntegrityError:
                st.error(f"❌ SKU '{sku}' sudah ada! Gunakan form Restock di bawah untuk menambah stok.")
            except Exception as e:
                if "duplicate key" in str(e).lower():
                    st.error(f"❌ SKU '{sku}' sudah ada! Gunakan form Restock di bawah untuk menambah stok.")
                else:
                    st.error(f"❌ Gagal menyimpan: {e}")

    daftar = df("SELECT sku, nama, stok, harga_beli FROM barang ORDER BY nama")
    section("📦", "Restock Barang Existing", "Tambah stok untuk barang yang sudah terdaftar")
    if daftar.empty:
        empty_state("Belum ada barang — tambahkan master barang terlebih dahulu di atas.", "🏷️")
    else:
        with st.form("form_restock", clear_on_submit=True):
            pilih = st.selectbox("Pilih Barang", daftar.apply(lambda r: f"{r['sku']} — {r['nama']} (Stok: {int(r['stok'])})", axis=1))
            col1, col2 = st.columns(2)
            jml_masuk = col1.number_input("Jumlah Unit Masuk", min_value=1, step=1, value=1)
            catatan = col2.text_input("Catatan (mis. nama supplier)", placeholder="mis. PT Sumber Makmur")
            kirim = st.form_submit_button("📥 Catat Barang Masuk", type="primary", use_container_width=True)

        if kirim:
            sku_pick = pilih.split(" — ")[0].strip()
            run("UPDATE barang SET stok = stok + ? WHERE sku = ?", (int(jml_masuk), sku_pick))
            run(
                "INSERT INTO barang_masuk (sku, jumlah, catatan, tanggal) VALUES (?,?,?,?)",
                (sku_pick, int(jml_masuk), catatan.strip(), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            )
            st.session_state["toast_ok"] = f"✅ Restock {int(jml_masuk)} unit untuk {sku_pick} berhasil dicatat!"
            st.rerun()

    masuk = df("SELECT tanggal, sku, jumlah, catatan FROM barang_masuk ORDER BY id DESC LIMIT 15")
    if not masuk.empty:
        section("🧮", "Riwayat Barang Masuk", "15 catatan terakhir")
        mk = masuk.rename(columns={"tanggal": "Tanggal", "sku": "SKU", "jumlah": "Qty Masuk", "catatan": "Catatan"})
        st.table(mk)

    section("🗄️", "Tabel Master Stok", "Seluruh data barang dengan pencarian")
    cari = st.text_input("🔍 Cari (SKU / Nama / Kategori)", label_visibility="collapsed", placeholder="🔍 Ketik untuk mencari barang...")
    master = df("SELECT * FROM barang ORDER BY nama")
    if cari:
        q = cari.lower()
        master = master[
            master["sku"].str.lower().str.contains(q)
            | master["nama"].str.lower().str.contains(q)
            | master["kategori"].fillna("").str.lower().str.contains(q)
        ]

    if master.empty:
        empty_state("Tidak ada data barang yang cocok dengan pencarian.", "🔍")
    else:
        md = master.copy()
        md.columns = ["SKU", "Nama Barang", "Kategori", "Harga Beli", "Harga Jual Grosir", "Stok", "Limit Alert"]
        md["Harga Beli"] = md["Harga Beli"].map(rupiah)
        md["Harga Jual Grosir"] = md["Harga Jual Grosir"].map(rupiah)
        md["Status"] = master.apply(lambda r: "🔴 Menipis" if r["stok"] <= r["limit_alert"] else "🟢 Aman", axis=1)
        md.index += 1
        st.dataframe(md, use_container_width=True)


# ============================================================
#  3) BARANG KELUAR / POS KASIR
# ============================================================
elif menu.startswith("📤"):

    page_title("Barang Keluar / POS Kasir", "Toko Grosir", "Catat penjualan grosir — kalkulasi otomatis & stok terpotong real-time")

    barang = df("SELECT sku, nama, stok, harga_beli, harga_jual, limit_alert FROM barang ORDER BY nama")
    if barang.empty:
        empty_state("Belum ada master barang — buka menu 'Barang Masuk / Restock' dulu ya.", "🏷️")
        qa = st.columns(2)
        if qa[0].button("📥 Ke Menu Restock", use_container_width=True, type="primary"):
            goto("📥 Barang Masuk / Restock")
    else:
        pos, side = st.columns([2, 1])

        with pos:
            with st.form("form_pos", clear_on_submit=True):
                pilihan = st.selectbox(
                    "🛒 Pilih Barang",
                    barang.apply(lambda r: f"{r['sku']} — {r['nama']} (Stok: {int(r['stok'])})", axis=1),
                )
                opt = st.columns([1, 1, 2])
                qty = opt[0].number_input("Qty (karton/bal/kg)", min_value=1, step=1, value=1)
                diskon_unit = opt[1].number_input("Diskon /unit (Rp)", min_value=0, step=100, help="Diskon per unit (opsional)")
                pelanggan = opt[2].text_input("Nama Pelanggan (opsional)", placeholder="mis. Warung Bu Sari")

                # preview kalkulasi
                sku_pick = pilihan.split(" — ")[0].strip()
                row = barang[barang["sku"] == sku_pick].iloc[0]
                st.caption(
                    f"**Info barang:** stok {int(row['stok'])} · h. beli {rupiah(row['harga_beli'])} · "
                    f"h. jual {rupiah(row['harga_jual'])}"
                )
                h_jual_net = max(0, row["harga_jual"] - diskon_unit)
                pr_omzet = h_jual_net * qty
                pr_hpp = row["harga_beli"] * qty
                pr_laba = pr_omzet - pr_hpp
                pv = st.columns(3)
                with pv[0]:
                    mini_stat("💵 Omzet (Penjualan)", rupiah(pr_omzet), "#4F46E5")
                with pv[1]:
                    mini_stat("📦 HPP / Modal", rupiah(pr_hpp), "#D97706")
                with pv[2]:
                    mini_stat("🟢 Untung (Laba)", rupiah(pr_laba), "#059669")

                jual = st.form_submit_button("💰 Proses Penjualan & Potong Stok", type="primary", use_container_width=True)

            if jual:
                if qty > row["stok"]:
                    st.error(f"❌ Stok tidak cukup! Sisa stok {int(row['stok'])} unit.")
                else:
                    run("UPDATE barang SET stok = stok - ? WHERE sku = ?", (int(qty), sku_pick))
                    run(
                        "INSERT INTO barang_keluar (sku, jumlah, harga_beli, harga_jual, omzet, laba, pelanggan, tanggal) VALUES (?,?,?,?,?,?,?,?)",
                        (
                            sku_pick,
                            int(qty),
                            float(row["harga_beli"]),
                            float(h_jual_net),
                            float(pr_omzet),
                            float(pr_laba),
                            pelanggan.strip(),
                            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        ),
                    )
                    st.session_state["toast_ok"] = (
                        f"✅ Transaksi sukses! {int(qty)} unit {sku_pick} terjual — omzet {rupiah(pr_omzet)}, laba {rupiah(pr_laba)}."
                    )
                    st.rerun()

        with side:
            section("📦", "Cek Stok Live")
            hasil = df("SELECT nama, stok, limit_alert FROM barang WHERE sku = ?", (sku_pick,))
            if not hasil.empty:
                r0 = hasil.iloc[0]
                kpi_card(r0["nama"], f"{int(r0['stok'])} unit", "box", "#475569", "Stok tersisa saat ini")
                if r0["stok"] <= r0["limit_alert"]:
                    st.error("⚠️ Stok menyentuh limit alert!")
                kotak = int(r0["stok"])
                if kotak > 0:
                    st.progress(min(100, kotak * 5 + 5), text=f"{kotak} unit tersisa")

            section("🧾", "Struk Terakhir")
            last = df("SELECT * FROM barang_keluar ORDER BY id DESC LIMIT 1")
            if not last.empty:
                r = last.iloc[0]
                st.markdown(
                    f"""
                    | Struk #{int(r['id'])} | |
                    |---|---|
                    | SKU | {r['sku']} |
                    | Qty | {int(r['jumlah'])} |
                    | Harga Jual | {rupiah(r['harga_jual'])} |
                    | **Omzet** | **{rupiah(r['omzet'])}** |
                    | **Laba** | **{rupiah(r['laba'])}** |
                    | Pelanggan | {r['pelanggan'] or '-'} |
                    | Waktu | {r['tanggal']} |
                    """
                )
            else:
                empty_state("Belum ada penjualan hari ini.", "🧾")

    section("📚", "Riwayat Penjualan", "20 transaksi terakhir")
    keluar = df("SELECT tanggal, sku, jumlah, harga_beli, harga_jual, omzet, laba, pelanggan FROM barang_keluar ORDER BY id DESC LIMIT 20")
    if keluar.empty:
        empty_state("Belum ada transaksi penjualan.", "🛒")
    else:
        kj = keluar.rename(
            columns={
                "tanggal": "Tanggal", "sku": "SKU", "jumlah": "Qty",
                "harga_beli": "H. Beli", "harga_jual": "H. Jual",
                "omzet": "Omzet", "laba": "Laba", "pelanggan": "Pelanggan",
            }
        )
        for kol in ["H. Beli", "H. Jual", "Omzet", "Laba"]:
            kj[kol] = kj[kol].map(rupiah)
        kj.index += 1
        st.dataframe(kj, use_container_width=True)


# ============================================================
#  4) LAPORAN LABA RUGI (P&L)
# ============================================================
else:

    page_title("Laporan Laba Rugi (P&L)", "Toko Grosir", "Pendapatan − HPP − Biaya Operasional = Laba Bersih Akhir")

    col_t1, col_t2 = st.columns(2)
    tgl_awal = col_t1.date_input("📅 Dari Tanggal", value=date.today().replace(day=1))
    tgl_akhir = col_t2.date_input("📅 Sampai Tanggal", value=date.today())

    if tgl_akhir < tgl_awal:
        st.error("❌ 'Sampai tanggal' tidak boleh lebih awal dari 'Dari tanggal'.")
        st.stop()

    p_awal, p_akhir = tgl_awal.strftime("%Y-%m-%d 00:00:00"), tgl_akhir.strftime("%Y-%m-%d 23:59:59")

    pendapatan = df(
        "SELECT COALESCE(SUM(omzet),0) AS t FROM barang_keluar WHERE tanggal BETWEEN ? AND ?",
        (p_awal, p_akhir),
    ).iloc[0]["t"]
    hpp = df(
        "SELECT COALESCE(SUM(harga_beli * jumlah),0) AS t FROM barang_keluar WHERE tanggal BETWEEN ? AND ?",
        (p_awal, p_akhir),
    ).iloc[0]["t"]
    laba_kotor = pendapatan - hpp

    # -- Penambahan biaya operasional --
    with st.expander("➕ Tambah Biaya Operasional", expanded=False):
        with st.form("form_biaya", clear_on_submit=True):
            kol1, kol2 = st.columns([2, 1])
            ket = kol1.text_input("Keterangan Biaya", placeholder="mis. Gaji karyawan, Listrik, Delivery")
            jumlah_biaya = kol2.number_input("Jumlah (Rp)", min_value=0, step=5000, value=50000)
            flag = st.form_submit_button("💾 Simpan Biaya Operasional", type="primary", use_container_width=True)
        if flag:
            if not ket.strip() or jumlah_biaya <= 0:
                st.error("❌ Keterangan dan jumlah biaya wajib diisi.")
            else:
                run(
                    "INSERT INTO biaya_operasional (keterangan, jumlah, tanggal) VALUES (?,?,?)",
                    (ket.strip(), float(jumlah_biaya), datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                )
                st.session_state["toast_ok"] = f"✅ Biaya operasional '{ket}' tersimpan."
                st.rerun()

    biaya_ops = df(
        "SELECT COALESCE(SUM(jumlah),0) AS t FROM biaya_operasional WHERE tanggal BETWEEN ? AND ?",
        (p_awal, p_akhir),
    ).iloc[0]["t"]
    laba_bersih = laba_kotor - biaya_ops
    margin_pl = 0 if pendapatan == 0 else laba_bersih / pendapatan * 100

    section("📊", "Ringkasan Periode")
    r1 = st.columns(4)
    with r1[0]:
        kpi_card("Pendapatan", rupiah(pendapatan), "cash", "#4F46E5")
    with r1[1]:
        kpi_card("HPP", rupiah(hpp), "box", "#D97706")
    with r1[2]:
        kpi_card("Laba Kotor", rupiah(laba_kotor), "wallet", "#0D9488")
    with r1[3]:
        kpi_card("Laba Bersih", rupiah(laba_bersih), "chart", "#059669", f"Margin {margin_pl:.1f}%")

    section("🧾", "Statement Laba Rugi", f"Periode {tgl_awal.strftime('%d/%m/%Y')} — {tgl_akhir.strftime('%d/%m/%Y')}")
    st.markdown(
        f"""
        <div class="plcard">
          <div class="plrow"><span>Pendapatan (Omzet Penjualan)</span><span class="plval">{rupiah(pendapatan)}</span></div>
          <div class="plrow minus"><span>HPP / Harga Pokok Penjualan</span><span class="plval">− {rupiah(hpp)}</span></div>
          <div class="plrow"><span><b>Laba Kotor</b></span><span class="plval">{rupiah(laba_kotor)}</span></div>
          <div class="plrow minus"><span>Biaya Operasional</span><span class="plval">− {rupiah(biaya_ops)}</span></div>
          <div class="plrow total"><span>LABA BERSIH AKHIR</span><span class="plval">{rupiah(laba_bersih)}</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # -- Detail biaya --
    detail_biaya = df(
        "SELECT tanggal, keterangan, jumlah FROM biaya_operasional WHERE tanggal BETWEEN ? AND ? ORDER BY id DESC",
        (p_awal, p_akhir),
    )
    if not detail_biaya.empty:
        section("💸", "Rincian Biaya Operasional")
        dbl = detail_biaya.rename(columns={"tanggal": "Tanggal", "keterangan": "Keterangan", "jumlah": "Jumlah"})
        dbl["Jumlah"] = dbl["Jumlah"].map(rupiah)
        dbl.index += 1
        st.dataframe(dbl, use_container_width=True)

    # -- Export Excel & Cetak --
    st.divider()
    x1, x2 = st.columns([1, 1])

    excel_bio = io.BytesIO()
    with pd.ExcelWriter(excel_bio, engine="openpyxl") as writer:
        ringkasan = df(
            "SELECT sku, jumlah, harga_beli, harga_jual, omzet, laba, tanggal FROM barang_keluar WHERE tanggal BETWEEN ? AND ?",
            (p_awal, p_akhir),
        )
        ringkasan.to_excel(writer, index=False, sheet_name="Penjualan")
        detail_biaya.to_excel(writer, index=False, sheet_name="Biaya Operasional")
        pd.DataFrame(
            {
                "Komponen": ["Pendapatan", "HPP", "Laba Kotor", "Biaya Operasional", "Laba Bersih Akhir"],
                "Nilai (Rp)": [pendapatan, hpp, laba_kotor, biaya_ops, laba_bersih],
            }
        ).to_excel(writer, index=False, sheet_name="Ringkasan PL")
    excel_bio.seek(0)

    x1.download_button(
        label="📤 Export Excel",
        data=excel_bio,
        file_name=f"Laporan_Laba_Rugi_{tgl_awal}_{tgl_akhir}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
        type="primary",
    )

    with x2:
        st.components.v1.html(
            """
            <button onclick="window.print()" style="
                width:100%; padding:0.4rem 0.6rem; background:linear-gradient(135deg,#4f46e5,#7c3aed);
                color:white; border:none; border-radius:0.75rem; font-weight:600; cursor:pointer;
                font-family:'Inter','Segoe UI',sans-serif;
                box-shadow:0 10px 22px -8px rgba(79,70,229,.5);" >
                🖨️ Cetak Ringkasan
            </button>
            """,
            height=42,
        )

# ============================================================
#  TOAST GLOBAL
# ============================================================
if "toast_ok" in st.session_state:
    st.toast(st.session_state.pop("toast_ok"), icon="✅")
