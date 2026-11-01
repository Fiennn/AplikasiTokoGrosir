# -*- coding: utf-8 -*-
"""
Aplikasi Manajemen Stok Masuk Keluar & Laporan Laba Rugi — Toko Grosir
Stack : Streamlit + SQLite/PostgreSQL(Supabase) + Pandas
DB    : otomatis pakai Supabase jika ada secret SUPABASE_DB_URL,
        fallback ke SQLite lokal (grosir.db) jika tidak ada.
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


init_db()


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
#  DESAIN & KOMPONEN VISUAL
# ============================================================

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap');

.stApp{background:#f4f7fb;font-family:'Plus Jakarta Sans','Segoe UI',sans-serif;}
#MainMenu,footer,header{visibility:hidden;}
a:link,a:visited{color:#2563eb;}

/* ===== SIDEBAR ===== */
section[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#0b1e4b 0%,#1e3a8a 55%,#312e81 100%);
}
section[data-testid="stSidebar"] *{color:#dbeafe !important;}
.brand{display:flex;gap:12px;align-items:center;margin:6px 0 18px;}
.brand-ico{font-size:1.6rem;background:linear-gradient(135deg,#38bdf8,#6366f1);width:52px;height:52px;display:flex;align-items:center;justify-content:center;border-radius:14px;box-shadow:0 4px 14px rgba(56,189,248,.4);}
.brand h1{font-size:1.1rem;font-weight:800;margin:0 !important;line-height:1.2;}
.brand p{font-size:.72rem;opacity:.75;margin:2px 0 0 !important;}
.menulabel{font-size:.66rem;font-weight:800;letter-spacing:1.4px;text-transform:uppercase;opacity:.55;margin-bottom:8px;}
section[data-testid="stSidebar"] .stRadio [role=radiogroup]{gap:6px;}
section[data-testid="stSidebar"] .stRadio label{
  background:rgba(255,255,255,.06);border:1px solid rgba(255,255,255,.12);
  border-radius:12px;padding:11px 14px;font-weight:600;font-size:.88rem;
  transition:all .18s ease;min-height:0 !important;
}
section[data-testid="stSidebar"] .stRadio label:hover{background:rgba(255,255,255,.15);transform:translateX(3px);}
section[data-testid="stSidebar"] .stRadio label:has(input:checked){
  background:linear-gradient(90deg,#3b82f6,#6366f1);border-color:#60a5fa;
  box-shadow:0 4px 14px rgba(59,130,246,.45);
}
section[data-testid="stSidebar"] .stRadio [role=radiogroup] input{position:absolute;opacity:0;pointer-events:none;}
.sidechip{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);border-radius:10px;padding:8px 12px;font-size:.78rem;margin-top:6px;}

/* ===== JUDUL HALAMAN & SEKSI ===== */
.ptitle h1{font-size:1.75rem;font-weight:800;color:#0f172a;margin:0;}
.ptitle p{color:#64748b;font-size:.88rem;margin:4px 0 10px;}
.sechead{display:flex;align-items:center;gap:9px;font-size:1.05rem;font-weight:800;color:#1e293b;margin:20px 0 10px;}
.sechead::before{content:"";display:inline-block;width:5px;height:20px;border-radius:4px;background:linear-gradient(180deg,#3b82f6,#8b5cf6);}
.sechead small{font-weight:600;color:#94a3b8;font-size:.76rem;}

/* ===== KARTU KPI ===== */
.kpi-card{border-radius:18px;padding:18px 20px;color:#fff;box-shadow:0 10px 26px -8px rgba(2,20,60,.45);position:relative;overflow:hidden;min-height:146px;}
.kpi-card::after{content:"";position:absolute;right:-28px;top:-28px;width:110px;height:110px;border-radius:50%;background:rgba(255,255,255,.14);pointer-events:none;}
.kpi-ico{font-size:1.4rem;background:rgba(255,255,255,.22);width:46px;height:46px;display:flex;align-items:center;justify-content:center;border-radius:13px;margin-bottom:10px;}
.kpi-label{font-size:.76rem;font-weight:700;opacity:.9;letter-spacing:.4px;text-transform:uppercase;}
.kpi-val{font-size:1.5rem;font-weight:800;margin-top:2px;position:relative;z-index:1;}
.kpi-sub{font-size:.74rem;opacity:.85;margin-top:6px;}

/* ===== MINI STAT ===== */
.mstat{background:#fff;border:1px solid #e5eaf2;border-radius:14px;padding:12px 16px;box-shadow:0 2px 10px rgba(15,23,42,.06);border-top:4px solid #3b82f6;}
.mstat-l{font-size:.7rem;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.5px;}
.mstat-v{font-size:1rem;font-weight:800;color:#0f172a;margin-top:4px;}

/* ===== TOMBOL ===== */
div.stButton>button,div.stFormSubmitButton>button,div.stDownloadButton>button{
  border:none;border-radius:12px;font-weight:700;
  box-shadow:0 3px 12px rgba(37,99,235,.28);transition:all .18s ease;
}
div.stButton>button:hover,div.stFormSubmitButton>button:hover,div.stDownloadButton>button:hover{
  transform:translateY(-2px);box-shadow:0 7px 18px rgba(37,99,235,.4);
}

/* ===== TABEL ===== */
div[data-testid="stDataFrame"],div[data-testid="stTable"]{border-radius:14px;overflow:hidden;}

/* ===== STATEMEN LABA RUGI ===== */
.plcard{background:#fff;border:1px solid #e5eaf2;border-radius:18px;padding:6px 22px;box-shadow:0 4px 20px rgba(15,23,42,.07);max-width:760px;}
.plrow{display:flex;justify-content:space-between;align-items:center;padding:13px 0;border-bottom:1px dashed #e2e8f0;font-size:.95rem;color:#334155;}
.plrow .plval{font-weight:800;color:#0f172a;}
.plrow.minus .plval{color:#dc2626;}
.plrow.total{border-bottom:none;background:linear-gradient(90deg,rgba(22,163,74,.12),rgba(22,163,74,.02));margin:6px -22px 0;padding:16px 22px;border-radius:0 0 18px 18px;font-weight:800;color:#14532d;}
.plrow.total .plval{color:#15803d;font-size:1.25rem;}

/* ===== KOSONG & PROGRESS ===== */
.empty{background:#fff;border:2px dashed #cbd5e1;color:#64748b;text-align:center;border-radius:16px;padding:26px;font-weight:600;}
div.stProgress>div>div{background:linear-gradient(90deg,#f59e0b,#ef4444);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)


def page_title(emoji, text, caption_text):
    st.markdown(f'<div class="ptitle"><h1>{emoji} {text}</h1><p>{caption_text}</p></div>', unsafe_allow_html=True)


def section(emoji, text, note=""):
    small = f"<small>{note}</small>" if note else ""
    st.markdown(f'<div class="sechead">{emoji}&nbsp; {text}&nbsp;&nbsp;{small}</div>', unsafe_allow_html=True)


def kpi_card(label, value, emoji, grad, sub=""):
    st.markdown(
        f"""<div class="kpi-card" style="background:{grad};">
        <div class="kpi-ico">{emoji}</div>
        <div class="kpi-label">{label}</div>
        <div class="kpi-val">{value}</div>
        <div class="kpi-sub">{sub}</div></div>""",
        unsafe_allow_html=True,
    )


def mini_stat(label, value, color):
    st.markdown(
        f'<div class="mstat" style="border-top-color:{color};"><div class="mstat-l">{label}</div><div class="mstat-v">{value}</div></div>',
        unsafe_allow_html=True,
    )


def empty_state(text, icon="📭"):
    st.markdown(f'<div class="empty">{icon}&nbsp; {text}</div>', unsafe_allow_html=True)


def goto(label_menu):
    """Navigasi programatik: simpan target, halaman dulu baru ubah widget radio."""
    st.session_state["__nav_target"] = label_menu
    st.rerun()


# Terapkan target navigasi SEBELUM widget radio dibuat
if "__nav_target" in st.session_state:
    st.session_state["Navigasi"] = st.session_state.pop("__nav_target")


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
    db_label = "☁️ Database: Supabase" if IS_PG else "💾 Database: SQLite lokal"
    st.sidebar.markdown(f'<div class="sidechip">🗄️ {db_label}</div>', unsafe_allow_html=True)
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

    page_title("📊", "Dashboard Toko Grosir", "Ringkasan performa bisnis secara real-time")

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
        kpi_card("Total Omzet", rupiah(omzet), "💵",
                 "linear-gradient(135deg,#0ea5e9,#2563eb)")
    with r1[1]:
        kpi_card("Total HPP / Modal", rupiah(hpp), "📦",
                 "linear-gradient(135deg,#f59e0b,#ea580c)")
    with r1[2]:
        kpi_card("Laba Bersih", rupiah(laba_bersih), "🏆",
                 "linear-gradient(135deg,#22c55e,#15803d)",
                 f"Margin {margin:.1f}%")
    with r1[3]:
        kpi_card("Jumlah SKU", f"{int(jml_sku)} item", "🏷️",
                 "linear-gradient(135deg,#8b5cf6,#6d28d9)")

    r2 = st.columns(2)
    with r2[0]:
        mini_stat("Nilai Persediaan (Modal)", rupiah(nilai_stok), "#6366f1")
    with r2[1]:
        mini_stat("Total Biaya Operasional", rupiah(biaya), "#ef4444")
    st.caption("💡 Laba bersih = Omzet − HPP − Biaya Operasional")

    # -- Peringatan stok menipis --
    section("⚠️", "Peringatan Stok Menipis", " Barang dengan stok di bawah limit")
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

    page_title("📥", "Barang Masuk / Restock", "Kelola master barang & catat penerimaan stok grosir")

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
    section("📦", "Restock Barang Existing", " Tambah stok untuk barang yang sudah terdaftar")
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

    page_title("📤", "Barang Keluar / POS Kasir", "Catat penjualan grosir — kalkulasi otomatis & stok terpotong real-time")

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
                    mini_stat("💵 Omzet (Penjualan)", rupiah(pr_omzet), "#0ea5e9")
                with pv[1]:
                    mini_stat("📦 HPP / Modal", rupiah(pr_hpp), "#f59e0b")
                with pv[2]:
                    mini_stat("🟢 Untung (Laba)", rupiah(pr_laba), "#22c55e")

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
                kpi_card(r0["nama"], f"{int(r0['stok'])} unit", "📦",
                         "linear-gradient(135deg,#475569,#1e293b)",
                         "Stok tersisa saat ini")
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

    page_title("📈", "Laporan Laba Rugi (P&L)", "Pendapatan − HPP − Biaya Operasional = Laba Bersih Akhir")

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
        kpi_card("Pendapatan", rupiah(pendapatan), "💵", "linear-gradient(135deg,#0ea5e9,#2563eb)")
    with r1[1]:
        kpi_card("HPP", rupiah(hpp), "📦", "linear-gradient(135deg,#f59e0b,#ea580c)")
    with r1[2]:
        kpi_card("Laba Kotor", rupiah(laba_kotor), "🟩", "linear-gradient(135deg,#14b8a6,#0f766e)")
    with r1[3]:
        kpi_card("Laba Bersih", rupiah(laba_bersih), "🏆",
                 "linear-gradient(135deg,#22c55e,#15803d)", f"Margin {margin_pl:.1f}%")

    section("🧾", "Statement Laba Rugi", f"Periode {tgl_awal.strftime('%d/%m/%Y')} — {tgl_akhir.strftime('%d/%m/%Y')}")
    st.markdown(
        f"""
        <div class="plcard">
          <div class="plrow"><span>🟦 Pendapatan (Omzet Penjualan)</span><span class="plval">{rupiah(pendapatan)}</span></div>
          <div class="plrow minus"><span>🟧 HPP / Harga Pokok Penjualan</span><span class="plval">− {rupiah(hpp)}</span></div>
          <div class="plrow"><span>🟩 <b>Laba Kotor</b></span><span class="plval">{rupiah(laba_kotor)}</span></div>
          <div class="plrow minus"><span>🟥 Biaya Operasional</span><span class="plval">− {rupiah(biaya_ops)}</span></div>
          <div class="plrow total"><span>⭐ LABA BERSIH AKHIR</span><span class="plval">{rupiah(laba_bersih)}</span></div>
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
        label="📥 Export Excel",
        data=excel_bio,
        file_name=f"Laporan_Laba_Rugi_{tgl_awal}_{tgl_akhir}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    with x2:
        st.components.v1.html(
            """
            <button onclick="window.print()" style="
                width:100%; padding:0.4rem 0.6rem; background:linear-gradient(135deg,#6366f1,#8b5cf6);
                color:white; border:none; border-radius:0.55rem; font-weight:700; cursor:pointer;
                box-shadow:0 3px 12px rgba(99,102,241,.4);" >
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
