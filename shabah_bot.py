import os
import re
import pandas as pd
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    ContextTypes,
    filters,
)

TOKEN = "8327163163:AAEI3uz6bG7uYXfl65J9vh0gtEuPJkf4hsE"


# ============================
# Extract product codes from SKU
# ============================
def extract_codes(sku):
    sku = str(sku)
    htb = fhm = fire_starter = hidroleck_package = bbq = inc = None

    m_htb = re.search(r'HTB(?:W?\d+Q?\d*T)?(\d+)', sku)
    if m_htb:
        htb = "HTB" + m_htb.group(1)

    m_fhm = re.search(r'FHM(\d+)', sku)
    if m_fhm:
        fhm = "FHM" + m_fhm.group(1)

    if re.search(r'FS_bag_Q20', sku):
        fire_starter = 'مشعل النار'

    if re.search(r'Car_Jack_5_ton', sku):
        hidroleck_package = 'طقم هايدروليك 3 في 1'

    if re.search(r'FHM-BBQ', sku):
        bbq = 'فحم الشواء'

    if re.search(r'FHM-INC', sku):
        inc = 'فحم البخور'

    return htb, fhm, fire_starter, hidroleck_package, bbq, inc


# ============================
# Parse اسماء المنتجات مع SKU
# ============================
def parse_names_column(cell):
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return []
    s = str(cell).replace("\n", " ").replace("\r", " ")
    matches = re.findall(
        r"\(SKU:\s*([A-Za-z0-9_]+)\).*?\(Qty:\s*(\d+)\)",
        s,
    )
    return [(sku, int(qty)) for sku, qty in matches]


# ============================
# Process File
# ============================
def process_file(input_path):
    df = pd.read_excel(input_path)

    if "اسماء المنتجات مع SKU" not in df.columns:
        raise Exception("الملف لا يحتوي على عمود اسماء المنتجات مع SKU")

    totals = {}

    def add_qty(key, qty):
        totals[key] = totals.get(key, 0) + qty

    for cell in df["اسماء المنتجات مع SKU"]:
        items = parse_names_column(cell)
        for sku, qty in items:
            htb, fhm, fire_starter, hidroleck_package, bbq, inc = extract_codes(sku)
            if htb:
                add_qty(htb, qty)
            if fhm:
                add_qty(fhm, qty)
            if fire_starter:
                add_qty(fire_starter, qty)
            if hidroleck_package:
                add_qty(hidroleck_package, qty)
            if bbq:
                add_qty(bbq, qty)
            if inc:
                add_qty(inc, qty)

    return (
        pd.DataFrame(
            [{"SKU": k, "الكمية": v} for k, v in totals.items()]
        )
        .sort_values("SKU")
    )


# ============================
# Telegram handlers
# ============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "مرحبًا! أرسل ملف طلبات شبة وسأحسب الكميات بناءً على (Qty)."
    )


async def file_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document
    input_path = None
    output_path = "Shabah_SKU_Report.xlsx"

    try:
        file_obj = await document.get_file()
        input_path = await file_obj.download_to_drive()

        df = process_file(input_path)
        df.to_excel(output_path, index=False)

        await update.message.reply_document(document=open(output_path, "rb"))
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ:\n{e}")
    finally:
        if input_path and os.path.exists(str(input_path)):
            os.remove(input_path)
        if os.path.exists(output_path):
            os.remove(output_path)


def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, file_handler))
    print("Shabah Bot is running...")
    app.run_polling()


if __name__ == "__main__":
    main()
