# Tennis Video-Sensor Fusion

Sprint 17 artifacts for stroke classification using video frames labeled with Zepp sensor data.

## Data Summary (Jan 3, 2026 Session)

| View | Frames | Swings | Duration |
|------|--------|--------|----------|
| Side | 312 | 20 | 62s |
| Back | 827 | 30 | 165s |

Zepp session: 50 total swings (18 FH, 23 BH, 9 Serve)

## Trained Model

`models/stroke_classifier_20260103_v2.pth` - MobileNetV3-small

- **Accuracy**: 87.5% on test set
- **Classes**: Forehand, Backhand, Serve (background excluded)
- **Input**: 224x224 RGB images

### Confusion Matrix (Test Set)
- Backhand: 83.3%
- Forehand: 85.7%
- Serve: 100%

## File Structure

```
Tennis/
├── models/
│   ├── stroke_classifier_20260103_v2.pth  # Best model
│   └── stroke_classifier_best.pth         # Symlink
├── artifacts/
│   └── training_history_20260103_v2.json  # Loss/accuracy curves
├── frames/
│   ├── 20260103_side/
│   │   ├── labels.csv      # frame_number,swing_type,zepp_swing_id
│   │   ├── manifest.csv    # frame_number,filename,timestamp_ms
│   │   └── metadata.json   # Sync offsets and timing notes
│   └── 20260103_back/
│       └── (same structure)
└── data/
    └── zepp_session_20260103.csv  # 50 swings with timestamps
```

## Sync Methodology

Frames extracted at 5 FPS. Zepp timestamps mapped to frames using manual visual sync:

```
frame_number = (zepp_epoch_ms - video_start_epoch_ms) / 200
```

**Current timing**: Frames show POST-CONTACT (ball visible leaving racket).

Metadata includes offsets for future adjustment:
- `pre_contact_offset_ms`: -400ms
- `at_contact_offset_ms`: -200ms
- `post_contact_offset_ms`: 0ms (current)

## Large Files (Not in Git)

Desktop can access directly:
- `ztennis.db` (208 MB) - Pull from rooted Avant: `/data/data/com.zepp.ztennis/databases/`
- Frame images - Re-extract from videos using ffmpeg at 5 FPS

## Usage

### Load Model for Inference
```python
import torch
import timm

model = timm.create_model('mobilenetv3_small_100', pretrained=False, num_classes=3)
model.load_state_dict(torch.load('models/stroke_classifier_20260103_v2.pth'))
model.eval()

# Classes: ['backhand', 'forehand', 'serve']
```

### Extract Frames from New Video
```bash
ffmpeg -i video.MOV -vf "fps=5" -q:v 2 frames/frame_%05d.jpg
```

## USB Transfer to Desktop

Desktop (RTX 3090) needs frames to generate full Sprint 16 artifacts.

### On Mac
```bash
# Prep USB with frames, videos, and Zepp database
python prep_usb.py /Volumes/YOUR_USB_NAME
```

### On Desktop
```bash
# Copy from USB
cp -r /run/media/blueaz/USB_NAME/Tennis_Transfer/* ~/Tennis/

# Generate missing artifacts (confusion matrix, embeddings, predictions)
cd ~/Python/project-phoenix/domains/TennisAgent/cockpit_poc/agent
python generate_artifacts.py ~/Tennis/frames/20260103_side/
```

### What Goes Where

| Machine | Role | Data |
|---------|------|------|
| **Mac** | Collection | Videos, frame extraction, AW app dev |
| **Desktop** | Analysis | Training (3090), Sprint 16 tools, artifacts |
| **Git** | Sync | Small artifacts (<10MB), code, labels |
| **USB** | Transfer | Frames, videos, databases (big files) |
