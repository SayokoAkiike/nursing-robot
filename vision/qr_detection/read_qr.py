"""
QRコード読み取りスクリプト (Day 8)
実行方法:
  画像ファイルから読む: python vision/qr_detection/read_qr.py --image path/to/image.png
  Webカメラから読む:   python vision/qr_detection/read_qr.py --camera
"""

import cv2
import argparse
import sys


def read_qr_from_image(image_path: str) -> str | None:
    """画像ファイルからQRコードを読み取る"""
    img = cv2.imread(image_path)
    if img is None:
        print(f"❌ 画像が読み込めません: {image_path}")
        return None

    detector = cv2.QRCodeDetector()
    data, points, _ = detector.detectAndDecode(img)

    if data:
        print(f"✅ QR読み取り成功: '{data}'")
        return data
    else:
        print("⚠️  QRコードを検出できませんでした")
        return None


def read_qr_from_camera():
    """WebカメラからリアルタイムでQRコードを読み取る"""
    print("📷 カメラ起動中... Qキーで終了")
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("❌ カメラが開けません（Codespaces環境ではカメラは使えません）")
        print("   画像ファイルを使ってください: --image path/to/qr.png")
        return

    detector = cv2.QRCodeDetector()
    last_detected = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        data, points, _ = detector.detectAndDecode(frame)

        if data and data != last_detected:
            print(f"✅ QR検出: '{data}'")
            last_detected = data

        # QR検出範囲を描画
        if points is not None:
            import numpy as np
            pts = points[0].astype(int)
            cv2.polylines(frame, [pts], True, (0, 255, 0), 2)
            if data:
                cv2.putText(frame, data, (pts[0][0], pts[0][1] - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("QR Reader (Press Q to quit)", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QRコード読み取りツール")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", help="読み取る画像ファイルのパス")
    group.add_argument("--camera", action="store_true", help="Webカメラを使う")
    args = parser.parse_args()

    if args.image:
        result = read_qr_from_image(args.image)
        if result:
            print(f"\n読み取ったID: {result}")
    elif args.camera:
        read_qr_from_camera()
