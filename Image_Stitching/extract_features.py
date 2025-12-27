import cv2
import numpy as np
import time


def extract_features(image_path_left, image_path_right, algorithm='SIFT'):
    img1 = cv2.imread(image_path_left)
    img2 = cv2.imread(image_path_right)

    if img1 is None or img2 is None:
        return None

    detectors = {
        'SIFT': cv2.SIFT_create(5000),
        'ORB': cv2.ORB_create(5000),
        'SURF': cv2.xfeatures2d.SURF_create(400) if hasattr(cv2, 'xfeatures2d') else cv2.SIFT_create(5000)
    }

    detector = detectors.get(algorithm, detectors['SIFT'])

    start = time.time()
    kp1, des1 = detector.detectAndCompute(img1, None)
    kp2, des2 = detector.detectAndCompute(img2, None)
    time_taken = time.time() - start

    return {
        'algorithm': algorithm,
        'kp1_count': len(kp1),
        'kp2_count': len(kp2),
        'time': time_taken,
        'img1': img1, 'img2': img2, 'kp1': kp1, 'kp2': kp2
    }


def compare_algorithms(image_path_left, image_path_right):
    algorithms = ['SIFT', 'ORB', 'SURF']
    results = []

    print("SO SÁNH THUẬT TOÁN")
    print("=" * 40)

    for algo in algorithms:
        result = extract_features(image_path_left, image_path_right, algo)
        if result:
            results.append(result)
            print(f"{algo}: {result['kp1_count']} + {result['kp2_count']} KP, {result['time']:.3f}s")

    # Hiển thị kết quả
    print(f"\nKẾT QUẢ:")
    best_kp = max(results, key=lambda x: x['kp1_count'] + x['kp2_count'])
    best_time = min(results, key=lambda x: x['time'])
    print(f"Nhiều KP nhất: {best_kp['algorithm']} ({best_kp['kp1_count'] + best_kp['kp2_count']} KP)")
    print(f"Nhanh nhất: {best_time['algorithm']} ({best_time['time']:.3f}s)")

    return results


def visualize_results(results):
    for result in results:
        algo = result['algorithm']
        img1_kp = cv2.drawKeypoints(result['img1'], result['kp1'], None, color=(0, 255, 0))
        img2_kp = cv2.drawKeypoints(result['img2'], result['kp2'], None, color=(0, 255, 0))

        cv2.imshow(f"{algo} - Ảnh 1", img1_kp)
        cv2.imshow(f"{algo} - Ảnh 2", img2_kp)

    cv2.waitKey(0)
    cv2.destroyAllWindows()


# CHẠY CHƯƠNG TRÌNH
if __name__ == "__main__":
    img_left = "image_left.jpg"
    img_right = "image_right.jpg"
    results = [extract_features(img_left,img_right)]
    # results = compare_algorithms(img_left, img_right)
    visualize_results(results)