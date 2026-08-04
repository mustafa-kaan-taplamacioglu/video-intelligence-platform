"""
Evaluate both model tiers on held-out test data.

Usage:
    python evaluate.py --models_dir ../models --test_video /path/to/test.mp4
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.services.activity_classifier import ActivityClassifier, Detection


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection models")
    parser.add_argument("--test_video", required=True, help="Path to test video")
    args = parser.parse_args()

    classifier = ActivityClassifier()
    print(f"Mode: {classifier.mode}")

    detections = classifier.analyze_video(args.test_video)
    print(f"\nDetections ({len(detections)}):")
    for d in detections:
        print(f"  [{d.start_time:.1f}s - {d.end_time:.1f}s] {d.label} ({d.confidence:.0%})")

    if not detections:
        print("  No suspicious activity detected.")


if __name__ == "__main__":
    main()
