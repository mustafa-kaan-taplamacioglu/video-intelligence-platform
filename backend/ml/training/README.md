# ML Model Training

Two-tier model system for suspicious activity detection.

## Architecture

| Tier | Model | Input | Output | Size |
|------|-------|-------|--------|------|
| **Tier 1** | MobileNetV2-035 | Raw frames 128x128 | Binary (normal/suspicious) | ~15MB |
| **Tier 2** | LSTM | MediaPipe pose sequences | 5-class (Normal, Shoplifting, Stealing, Burglary, Robbery) | ~2MB |

The system tries Tier 2 first, falls back to Tier 1, then to mock mode if neither exists.

## No Training Required

The app runs in **mock mode** by default — fake but realistic detections. You can use the full platform without training any model.

## Dataset

Download the DCSASS dataset from Kaggle:
https://www.kaggle.com/datasets/mateohervas/dcsass-dataset

## Training

### Tier 1: MobileNet Frame Classifier (faster to train)

```bash
pip install tensorflow tensorflow-hub scikit-learn pandas
python train_mobilenet.py --dcsass_root /path/to/DCSASS --output_dir ../models
```

Output: `../models/mobilenet_shoplifting.h5`

### Tier 2: MediaPipe Pose + LSTM (better accuracy)

```bash
pip install tensorflow mediapipe
python train_lstm.py --dcsass_root /path/to/DCSASS --output_dir ../models
```

Output: `../models/lstm_activity_classifier.keras`

### Evaluate

```bash
python evaluate.py --test_video /path/to/test_video.mp4
```

## Reference

The Tier 1 approach (MobileNetV2 frame classifier over DCSASS) was informed by a
publicly circulated Kaggle notebook on theft detection. The code here is an
independent implementation — see [NOTICE](../../../NOTICE) for the full
acknowledgement.

A notable limitation of that approach: it runs MediaPipe but never uses the
landmarks as model input — it classifies raw pixels. Tier 2 addresses this by
actually feeding pose landmarks into a temporal model.
