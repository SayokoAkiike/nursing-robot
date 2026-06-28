"""
QRコード生成スクリプト (Day 7)
実行方法: python vision/qr_detection/generate_qr.py
"""

import qrcode
import os

# ── 出力フォルダ ──────────────────────────────────────
OUTPUT_DIR = "vision/qr_detection/qr_images"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── 生成するQRコード一覧 ──────────────────────────────
QR_DATA = {
    # 患者ID
    "PATIENT_A_ROOM_203": "patient_a_room203.png",
    "PATIENT_B_ROOM_204": "patient_b_room204.png",
    # キットID
    "KIT_TOILETING_A":    "kit_toileting_a.png",
    "KIT_WATER":          "kit_water.png",
    "KIT_IV_ALERT":       "kit_iv_alert.png",
}

def generate_qr(data: str, filename: str):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=4,
    )
    qr.add_data(data)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    path = os.path.join(OUTPUT_DIR, filename)
    img.save(path)
    print(f"✅ 生成完了: {path}  (data='{data}')")

if __name__ == "__main__":
    print("=== QRコード生成開始 ===\n")
    for data, filename in QR_DATA.items():
        generate_qr(data, filename)
    print(f"\n📁 保存先: {OUTPUT_DIR}/")
    print("次のステップ: python vision/qr_detection/read_qr.py")
