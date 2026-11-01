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
#  SIDEBAR NAVIGASI
# ============================================================

st.sidebar.title("🏬 Toko Grosir")
st.sidebar.caption("Manajemen Stok & Laba Rugi")

menu = st.sidebar.radio(
    "Navigasi Menu",
    ["📊 Dashboard", "📥 Barang Masuk / Restock", "📤 Barang Keluar / POS Kasir", "📈 Laporan Laba Rugi (P&L)"],
)

st.sidebar.divider()
db_label = "☁️ Database: Supabase (permanen)" if IS_PG else "💾 Database: SQLite lokal"
st.sidebar.caption(db_label)
st.sidebar.write(f"📅 {datetime.now().strftime('%A, %d %B %Y')}")


# ============================================================
#  1) DASHBOARD
# ============================================================
if menu.startswith("📊"):

    st.title("📊 Dashboard Toko Grosir")
    st.caption("Ringkasan performa bisnis secara real-time")

    omzet = df("SELECT COALESCE(SUM(omzet),0)  AS t FROM barang_keluar").iloc[0]["t"]
    hpp = df(
        "SELECT COALESCE(SUM(harga_beli * jumlah),0) AS t FROM barang_keluar"
    ).iloc[0]["t"]
    biaya = df("SELECT COALESCE(SUM(jumlah),0) AS t FROM biaya_operasional").iloc[0]["t"]
    laba_bersih = omzet - hpp - biaya
    jml_sku = df("SELECT COUNT(*) AS t FROM barang").iloc[0]["t"]
    nilai_stok = df("SELECT COALESCE(SUM(harga_beli * stok),0) AS t FROM barang").iloc[0]["t"]

    st.subheader("💰 Performa Keuangan")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Omzet", rupiah(omzet))
    c2.metric("Total HPP / Modal", rupiah(hpp))
    c3.metric(
        "Laba Bersih",
        rupiah(laba_bersih),
        delta=f"Margin {0 if omzet == 0 else laba_bersih / omzet * 100:.1f}%",
        delta_color="normal",
    )
    c4.metric("Jumlah SKU", f"{int(jml_sku)} item")

    c1, c2, c3 = st.columns(3)
    c1.metric("Nilai Persediaan (Modal)", rupiah(nilai_stok))
    c2.metric("Total Biaya Operasional", rupiah(biaya))
    c3.caption("💡 Laba bersih = Omzet − HPP − Biaya Operasional")

    # --- Peringatan stok menipis ---
    st.subheader("⚠️ Peringatan Stok Menipis")
    rendah = df(
        "SELECT sku, nama, kategori, stok, limit_alert, harga_jual FROM barang WHERE stok <= limit_alert ORDER BY stok ASC"
    )
    if rendah.empty:
        st.success("✅ Semua stok barang aman, tidak ada yang menipis.")
    else:
        k1, k2, k3 = st.columns([2, 1, 3])
        k1.error(f"Ada {len(rendah)} SKU yang perlu segera direstock!")
        for _, r in rendah.iterrows():
            p = 100 if r["limit_alert"] <= 0 else min(100, max(4, int(r["stok"] / max(r["limit_alert"], 1) * 100)))
            with st.container(border=True):
                st.markdown(
                    f"**{r['sku']}** — {r['nama']}  \n"
                    f"Stok: **{int(r['stok'])}** (Limit alert: {int(r['limit_alert'])}) · "
                    f"Harga jual: {rupiah(r['harga_jual'])}"
                )
                st.progress(p, text=f"Stok {int(r['stok'])} / {int(r['limit_alert'])}")

    # --- Transaksi terbaru ---
    st.subheader("🧾 Transaksi Terbaru")
    terbaru = df(
        "SELECT tanggal, sku, jumlah, harga_jual, omzet, laba, pelanggan FROM barang_keluar ORDER BY id DESC LIMIT 8"
    )
    if terbaru.empty:
        st.info("Belum ada transaksi penjualan.")
    else:
        tampil = terbaru.rename(
            columns={
                "tanggal": "Tanggal",
                "sku": "SKU",
                "jumlah": "Qty",
                "harga_jual": "H. Jual",
                "omzet": "Omzet",
                "laba": "Laba",
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

    st.title("📥 Barang Masuk / Restock")
    st.caption("Kelola master barang & catat penerimaan stok grosir")

    with st.expander("➕ Tambah Master Barang Baru", expanded=True):
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
                        st.session_state["toast_ok"] = f"✅ SKU {sku} tersimpan. Stok awal masuk {int(stok_awal)} unit."
                    else:
                        st.session_state["toast_ok"] = f"✅ SKU {sku} berhasil ditambahkan ke master barang."
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error(f"❌ SKU '{sku}' sudah ada! Gunakan menu Restock untuk menambah stok.")

    # --- Form restock untuk barang existing ---
    st.subheader("📦 Restock Barang Existing")
    daftar = df("SELECT sku, nama, stok, harga_beli FROM barang ORDER BY nama")
    if daftar.empty:
        st.info("Belum ada barang. Tambahkan master barang terlebih dahulu di atas.")
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

    # --- Riwayat restock ---
    masuk = df("SELECT tanggal, sku, jumlah, catatan FROM barang_masuk ORDER BY id DESC LIMIT 15")
    if not masuk.empty:
        st.subheader("🧮 Riwayat Barang Masuk")
        mk = masuk.rename(columns={"tanggal": "Tanggal", "sku": "SKU", "jumlah": "Qty Masuk", "catatan": "Catatan"})
        st.table(mk)

    # --- Master stok + pencarian ---
    st.subheader("🗄️ Tabel Master Stok")
    cari = st.text_input("🔍 Cari (SKU / Nama / Kategori)", placeholder="ketik untuk mencari...")
    master = df("SELECT * FROM barang ORDER BY nama")
    if cari:
        q = cari.lower()
        master = master[
            master["sku"].str.lower().str.contains(q)
            | master["nama"].str.lower().str.contains(q)
            | master["kategori"].fillna("").str.lower().str.contains(q)
        ]

    if master.empty:
        st.info("Tidak ada data barang yang cocok.")
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

    st.title("📤 Barang Keluar / POS Kasir")
    st.caption("Catat penjualan grosir — omzet & laba terhitung otomatis, stok berkurang real-time")

    barang = df("SELECT sku, nama, stok, harga_beli, harga_jual, limit_alert FROM barang ORDER BY nama")
    if barang.empty:
        st.info("Belum ada master barang. Buka menu 'Barang Masuk / Restock' terlebih dahulu.")
    else:
        left, right = st.columns([2, 1])

        with left:
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
                st.markdown(f"**Info barang:** stok {int(row['stok'])} · h. beli {rupiah(row['harga_beli'])} · h. jual {rupiah(row['harga_jual'])}")
                h_jual_net = max(0, row["harga_jual"] - diskon_unit)
                pr_omzet = h_jual_net * qty
                pr_hpp = row["harga_beli"] * qty
                pr_laba = pr_omzet - pr_hpp
                p1, p2, p3 = st.columns(3)
                p1.metric("💵 Omzet (Penjualan)", rupiah(pr_omzet))
                p2.metric("📦 HPP / Modal", rupiah(pr_hpp))
                p3.metric("🟢 Untung (Laba)", rupiah(pr_laba))

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
                        f"✅ Transaksi sukses! {int(qty)} unit {sku_pick} terjual — Omzet {rupiah(pr_omzet)}, Laba {rupiah(pr_laba)}. Stok otomatis berkurang."
                    )
                    st.rerun()

        with right:
            st.subheader("☑️ Cek Stok Live")
            hasil = df("SELECT nama, stok, limit_alert FROM barang WHERE sku = ?", (sku_pick,))
            if not hasil.empty:
                r0 = hasil.iloc[0]
                st.metric(f"Stok {r0['nama']}", f"{int(r0['stok'])} unit")
                if r0["stok"] <= r0["limit_alert"]:
                    st.error("⚠️ Stok menyentuh limit alert!")
                kotak = int(r0["stok"])
                st.progress(min(100, kotak * 5 + 5) if kotak > 0 else 0, text=f"{kotak} unit tersisa")

            st.subheader("🧾 Struk Terakhir")
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

    # --- Riwayat penjualan ---
    st.subheader("📚 Riwayat Penjualan (Barang Keluar)")
    keluar = df("SELECT tanggal, sku, jumlah, harga_beli, harga_jual, omzet, laba, pelanggan FROM barang_keluar ORDER BY id DESC LIMIT 20")
    if keluar.empty:
        st.info("Belum ada transaksi penjualan.")
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

    st.title("📈 Laporan Laba Rugi (P&L)")
    st.caption("Pendapatan − HPP − Biaya Operasional = Laba Bersih Akhir")

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

    # --- Penambahan biaya operasional ---
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

    # --- Tabel P&L ---
    st.subheader("🧾 Laporan Laba Rugi")
    pl = pd.DataFrame(
        {
            "Komponen": [
                "Pendapatan (Omzet Penjualan)",
                "HPP / Harga Pokok Penjualan",
                "Laba Kotor",
                "(−) Biaya Operasional",
                "LABA BERSIH AKHIR",
            ],
            "Nilai (Rp)": [pendapatan, hpp, laba_kotor, biaya_ops, laba_bersih],
        }
    )
    pl.index += 1

    pl_fmt = pl.copy()
    pl_fmt["Nilai (Rp)"] = pl["Nilai (Rp)"].map(rupiah)
    highlight = {1: "🟦", 2: "🟧", 3: "🟩", 4: "🟥", 5: "⭐"}
    pl_fmt["Komponen"] = pl_fmt.apply(lambda r: f"{highlight.get(r.name, '')} {r['Komponen']}", axis=1)
    st.table(pl_fmt)

    k_1, k_2, k_3, k_4 = st.columns(4)
    k_1.metric("🟦 Pendapatan", rupiah(pendapatan))
    k_2.metric("🟧 HPP", rupiah(hpp))
    k_3.metric("🟩 Laba Kotor", rupiah(laba_kotor))
    k_4.metric(
        "🟨 Laba Bersih",
        rupiah(laba_bersih),
        delta=f"Margin {0 if pendapatan == 0 else laba_bersih / pendapatan * 100:.1f}%",
        delta_color="normal",
    )

    # --- Detail biaya ---
    detail_biaya = df(
        "SELECT tanggal, keterangan, jumlah FROM biaya_operasional WHERE tanggal BETWEEN ? AND ? ORDER BY id DESC",
        (p_awal, p_akhir),
    )
    if not detail_biaya.empty:
        st.subheader("💸 Rincian Biaya Operasional")
        dbl = detail_biaya.rename(columns={"tanggal": "Tanggal", "keterangan": "Keterangan", "jumlah": "Jumlah"})
        dbl["Jumlah"] = dbl["Jumlah"].map(rupiah)
        dbl.index += 1
        st.dataframe(dbl, use_container_width=True)

    # --- Export Excel & Cetak ---
    st.divider()
    x1, x2, x3 = st.columns([1, 1, 2])

    # Siapkan file Excel
    excel_bio = io.BytesIO()
    with pd.ExcelWriter(excel_bio, engine="openpyxl") as writer:
        ringkasan = df(
            "SELECT sku, jumlah, harga_beli, harga_jual, omzet, laba, tanggal FROM barang_keluar WHERE tanggal BETWEEN ? AND ?",
            (p_awal, p_akhir),
        )
        ringkasan.to_excel(writer, index=False, sheet_name="Penjualan")
        detail_biaya.to_excel(writer, index=False, sheet_name="Biaya Operasional")
        pl.to_excel(writer, index=False, sheet_name="Ringkasan PL")
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
                width:100%; padding:0.35rem 0.6rem; background:#ffb02e; color:black;
                border:2px solid #ffb02e; border-radius:0.3rem; font-weight:600; cursor:pointer;" >
                🖨️ Cetak Ringkasan
            </button>
            """,
            height=42,
        )

    st.caption(
        f"Laporan periode {tgl_awal.strftime('%d/%m/%Y')} — {tgl_akhir.strftime('%d/%m/%Y')}. "
        "Export Excel berisi sheet: Ringkasan PL, Penjualan, dan Biaya Operasional."
    )

# ============================================================
#  TOAST GLOBAL
# ============================================================
if "toast_ok" in st.session_state:
    st.toast(st.session_state.pop("toast_ok"), icon="✅")
