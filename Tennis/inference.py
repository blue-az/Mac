#!/usr/bin/env python3
"""
Run stroke classification inference on frames.

Usage:
    python inference.py <frames_dir> [--model stroke_classifier_best.pth]
    python inference.py ~/Tennis/frames/20260103_side/ --output predictions.csv

Example output:
    frame_0100.jpg,forehand,0.92
    frame_0101.jpg,forehand,0.87
    frame_0230.jpg,backhand,0.95
"""

import argparse
import csv
import sys
from pathlib import Path

import torch
import timm
from PIL import Image
from torchvision import transforms

# Model config
MODEL_NAME = "mobilenetv3_small_100"
CLASSES = ["backhand", "forehand", "serve"]
INPUT_SIZE = 224

# Image transforms (same as training)
transform = transforms.Compose([
    transforms.Resize((INPUT_SIZE, INPUT_SIZE)),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
])


def load_model(model_path):
    """Load trained model."""
    model = timm.create_model(MODEL_NAME, pretrained=False, num_classes=len(CLASSES))
    model.load_state_dict(torch.load(model_path, map_location="cpu"))
    model.eval()
    return model


def predict_frame(model, image_path):
    """Predict stroke type for a single frame."""
    img = Image.open(image_path).convert("RGB")
    tensor = transform(img).unsqueeze(0)

    with torch.no_grad():
        outputs = model(tensor)
        probs = torch.softmax(outputs, dim=1)
        confidence, predicted = torch.max(probs, 1)

    return CLASSES[predicted.item()], confidence.item()


def main():
    parser = argparse.ArgumentParser(description="Stroke classification inference")
    parser.add_argument("frames_dir", help="Directory containing frame JPGs")
    parser.add_argument("--model", default=None, help="Path to model .pth file")
    parser.add_argument("--output", default=None, help="Output CSV path")
    parser.add_argument("--threshold", type=float, default=0.5, help="Confidence threshold")
    args = parser.parse_args()

    frames_dir = Path(args.frames_dir)

    # Find model
    if args.model:
        model_path = Path(args.model)
    else:
        # Look in Tennis/models/
        tennis_dir = Path(__file__).parent
        model_path = tennis_dir / "models" / "stroke_classifier_best.pth"

    if not model_path.exists():
        print(f"Model not found: {model_path}")
        sys.exit(1)

    print(f"Loading model: {model_path}")
    model = load_model(model_path)

    # Find frames
    frames = sorted(frames_dir.glob("frame_*.jpg"))
    if not frames:
        print(f"No frames found in {frames_dir}")
        sys.exit(1)

    print(f"Processing {len(frames)} frames...")

    # Run inference
    results = []
    for frame_path in frames:
        stroke, confidence = predict_frame(model, frame_path)
        results.append({
            "frame": frame_path.name,
            "prediction": stroke,
            "confidence": round(confidence, 3)
        })

        if confidence >= args.threshold:
            print(f"  {frame_path.name}: {stroke} ({confidence:.1%})")

    # Save results
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = frames_dir / "predictions.csv"

    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["frame", "prediction", "confidence"])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nSaved {len(results)} predictions to {output_path}")

    # Summary
    from collections import Counter
    counts = Counter(r["prediction"] for r in results if r["confidence"] >= args.threshold)
    print(f"\nSummary (confidence >= {args.threshold}):")
    for stroke, count in counts.most_common():
        print(f"  {stroke}: {count}")


if __name__ == "__main__":
    main()
