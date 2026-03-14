import serial
import time
import threading
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ── Config ───
SERIAL_PORT   = "/dev/ttyUSB0"
BAUD_RATE     = 9600
TELEGRAM_TOKEN = "BOT_TOKEN"
ALLOWED_USER   = "Melvinz"  # username Telegram yang boleh kontrol

# Threshold
JARAK_WAJAN   = 20   # cm, kalau < ini dianggap ada wajan
JARAK_MAX     = 200  # cm, batas maksimal sensor ultrasonik

logging.basicConfig(
    format="%(asctime)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# ── State ───
state = {
    "jarak"        : 0.0,
    "api"          : False,
    "relay"        : False,
    "buzzer"       : False,
    "ada_wajan"    : False,
    "bahaya"       : False,
    "mode"         : "AUTO",   # AUTO | MANUAL
}

ser = None

# ── Serial ───
def kirim_perintah(device: str, value: int):
    if ser and ser.is_open:
        cmd = f"CMD:{device},{value}\n"
        ser.write(cmd.encode())
        logging.info(f"Kirim: {cmd.strip()}")

def parse_serial(line: str):
    # Format CSV: DATA,<jarak>,<api>,<relay>,<buzzer>
    line = line.strip()
    if not line.startswith("DATA,"):
        return
    try:
        _, jarak, api, relay, buzzer = line.split(",")
        state["jarak"]     = float(jarak)
        state["api"]       = bool(int(api))
        state["relay"]     = not bool(int(relay))   # active LOW
        state["buzzer"]    = not bool(int(buzzer))  # active LOW
        state["ada_wajan"] = state["jarak"] < JARAK_WAJAN
    except (ValueError, TypeError):
        logging.warning(f"Format serial tidak valid: {line}")

def auto_control():
    """Logic otomatis — hanya jalan kalau mode AUTO."""
    if state["mode"] != "AUTO":
        return

    bahaya = state["api"]  # bisa tambah: or state["gas_berbahaya"]

    if bahaya:
        state["bahaya"] = True
        kirim_perintah("relay", 0)    # tutup solenoid → matiin gas
        kirim_perintah("buzzer", 1)   # nyalain alarm
    else:
        state["bahaya"] = False
        kirim_perintah("buzzer", 0)

        if state["ada_wajan"]:
            kirim_perintah("relay", 1)  # buka solenoid → nyalain gas
        else:
            kirim_perintah("relay", 0)  # tutup solenoid → matiin gas

def baca_serial():
    """Thread pembaca serial dari Arduino."""
    global ser
    while True:
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=2)
            logging.info("Serial terhubung.")
            while True:
                if ser.in_waiting:
                    line = ser.readline().decode("utf-8", errors="ignore")
                    parse_serial(line)
                    auto_control()
        except serial.SerialException as e:
            logging.error(f"Serial error: {e}, retry 3s...")
            time.sleep(3)

# ── Telegram helpers ────
def format_status() -> str:
    return (
        f"📊 *Status Sistem:*\n"
        f"Gas Berbahaya: {'⚠️ YA' if state['bahaya'] else '✅ TIDAK'}\n"
        f"Status Api: {'🔥 MENYALA' if state['api'] else '✅ PADAM'}\n"
        f"Jarak Ultrasonik: {state['jarak']:.1f} cm\n"
        f"Status Wajan: {'✅ ADA' if state['ada_wajan'] else '❌ TIDAK'}\n"
        f"Status Bahaya: {'⚠️ YA' if state['bahaya'] else '✅ TIDAK'}\n"
        f"Mode Operasi: *{state['mode']}*"
    )

def cek_akses(update: Update) -> bool:
    return update.effective_user.username == ALLOWED_USER

# ── Command handlers ───
async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    kirim_perintah("status", 1)
    time.sleep(0.5)
    await update.message.reply_text(format_status(), parse_mode="Markdown")

async def cmd_on(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    if state["bahaya"]:
        await update.message.reply_text("⚠️ Tidak bisa menyalakan — kondisi bahaya terdeteksi!")
        return
    state["mode"] = "MANUAL"
    kirim_perintah("relay", 1)
    await update.message.reply_text("✅ Kompor dinyalakan.")

async def cmd_off(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    kirim_perintah("relay", 0)
    await update.message.reply_text("✅ Kompor dimatikan.")

async def cmd_auto(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    state["mode"] = "AUTO"
    await update.message.reply_text("🔄 Mode otomatis diaktifkan.")

async def cmd_manual(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    state["mode"] = "MANUAL"
    await update.message.reply_text("🔧 Mode manual diaktifkan.")

async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not cek_akses(update): return
    help_text = (
        "*Daftar Perintah Bot Kompor:*\n"
        "/status - Lihat status sensor & sistem\n"
        "/on - Nyalakan kompor secara manual\n"
        "/off - Matikan kompor secara manual\n"
        "/auto - Aktifkan mode otomatis\n"
        "/manual - Nonaktifkan mode otomatis\n"
        "/help - Tampilkan bantuan ini"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

# ── Main ────
def main():
    # Jalankan thread serial di background
    t = threading.Thread(target=baca_serial, daemon=True)
    t.start()

    # Jalankan bot Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("on",     cmd_on))
    app.add_handler(CommandHandler("off",    cmd_off))
    app.add_handler(CommandHandler("auto",   cmd_auto))
    app.add_handler(CommandHandler("manual", cmd_manual))
    app.add_handler(CommandHandler("help",   cmd_help))

    logging.info("SmartIgniteControl siap dijalankan!")
    app.run_polling()

if __name__ == "__main__":
    main()
