# Gazebo Meter Locator Dataset

The training payload is intentionally stored outside Git:

```text
/var/lib/substation/datasets/synthetic/gazebo-meter/a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2/gazebo-meter-locator-v1.zip
```

Verify it before upload:

```bash
echo '0f22438f4fa1baacdb06c7f64be65b08f78fd1b83f0891ac14f2c28c6ca0af4f  /var/lib/substation/datasets/synthetic/gazebo-meter/a1532e097446a27c63654fb8159f7835955a41c1dc47008e04ace43eac1a82d2/gazebo-meter-locator-v1.zip' | sha256sum -c -
```

On AutoDL:

```bash
unzip gazebo-meter-locator-v1.zip
cd gazebo-meter-locator-v1
sha256sum -c SHA256SUMS
yolo detect train data=data.yaml model=yolo11n.pt imgsz=640 epochs=100 batch=8 device=0 workers=6 seed=42 patience=20
```

The only detector class is `0: meter`. The pressure range (`0-2 MPa`) and oil level range (`0-100 percent`) are asset configuration, not YOLO classes.
