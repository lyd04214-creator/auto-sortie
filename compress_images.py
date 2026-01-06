import os
from PIL import Image

# [설정]
INPUT_DIR = 'assets/images'        # 원본 이미지가 있는 폴더
OUTPUT_DIR = 'assets/images_lite'  # 압축된 이미지가 저장될 폴더 (자동생성)
MAX_SIZE = (1280, 1280)            # 최대 해상도 (FHD급 이하로 제한)
QUALITY = 80                       # 화질 (1~100, 80 정도면 충분)

def compress_images():
    # 1. 출력 폴더 생성
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"📂 폴더 생성 완료: {OUTPUT_DIR}")

    files = [f for f in os.listdir(INPUT_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg', '.tif', '.tiff'))]
    total_files = len(files)
    
    print(f"🚀 총 {total_files}개의 이미지 압축을 시작합니다...")

    for idx, filename in enumerate(files):
        try:
            # 경로 설정
            input_path = os.path.join(INPUT_DIR, filename)
            output_path = os.path.join(OUTPUT_DIR, filename)

            # 이미지 열기
            with Image.open(input_path) as img:
                # 2. 색상 모드 변환 (PNG 투명도 유지하되, 불필요한 정보 제거)
                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGBA")
                else:
                    img = img.convert("RGB")

                # 3. 리사이징 (원본 비율 유지하면서 크기만 줄임)
                img.thumbnail(MAX_SIZE, Image.LANCZOS)

                # 4. 저장 (최적화 옵션 적용)
                # PNG는 quality 옵션이 없으므로 optimize=True 사용
                if filename.lower().endswith('.png'):
                    # PNG가 너무 크면 강제로 JPEG로 변환해서 저장할 수도 있지만,
                    # 코드 수정을 안 하려면 포맷 유지 추천. 대신 optimize로 용량 감소.
                    img.save(output_path, optimize=True, quality=QUALITY)
                else:
                    img.save(output_path, optimize=True, quality=QUALITY)

            print(f"[{idx+1}/{total_files}] ✅ 변환 완료: {filename}")

        except Exception as e:
            print(f"❌ 실패 ({filename}): {e}")

    print("\n🎉 모든 작업이 완료되었습니다!")
    print(f"확인: {OUTPUT_DIR} 폴더를 확인하세요.")

if __name__ == '__main__':
    compress_images()