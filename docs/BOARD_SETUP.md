# Board Setup: Arduino Nano 33 BLE Sense + OV7675

## Hardware

| Part | Notes |
|---|---|
| Arduino Nano 33 BLE Sense (Rev1 or Rev2) | nRF52840, 256 KB RAM. The sketch drives the camera pins on the nRF52 directly. |
| OV7675 camera module | For example, the camera from the Arduino *Tiny Machine Learning Kit*, mounted on its shield. |
| USB cable (data-capable) | Also carries the serial stream to the gateway PC. |

Mount the camera **fixed and still**, with the whole area the pet uses in view. The 96×96 frame is split into a 2×2 grid of zones, so the framing decides what a "zone transition" means. Keep the position identical between calibration and monitoring.

## Software

1. Install the **Arduino IDE 2.x** (or `arduino-cli`).
2. Install the board core **Arduino Mbed OS Nano Boards** (`arduino:mbed_nano`) from the Boards Manager.
3. Install the library **Arduino_OV767X** from the Library Manager.
4. Install the Edge Impulse model library from this repo:
   - **IDE:** zip the folder `edge-impulse-lib/CodeAbbas-project-1_inferencing/` and choose *Sketch → Include Library → Add .ZIP Library…*.
   - **Manual:** copy that folder into your Arduino `libraries/` directory, for example `Documents/Arduino/libraries/`.
   - **CLI:** `arduino-cli lib install --zip-path CodeAbbas-project-1_inferencing.zip`. This needs `library.enable_unsafe_install: true`.
5. Open `firmware/nano_ble33_sense_camera/nano_ble33_sense_camera.ino`, select **Arduino Nano 33 BLE**, and upload.

The first compile of the Edge Impulse SDK takes several minutes. This is normal.

```bash
# arduino-cli equivalent
arduino-cli compile --fqbn arduino:mbed_nano:nano33ble firmware/nano_ble33_sense_camera
arduino-cli upload  --fqbn arduino:mbed_nano:nano33ble -p COM10 firmware/nano_ble33_sense_camera
```

## Verify

Open the Serial Monitor. The baud rate doesn't matter for native USB CDC, but the gateway uses 115200. You should see:

```
Edge Impulse Inferencing Demo
D,48,40,0.8984,123456
N,-1,-1,0,126543
...
```

- `setup()` blocks on `while (!Serial);`, so **nothing runs until a serial host connects**. Delete that line if the board has to run without a host connected.
- To print per-frame timing lines (prefixed `#`, which the gateway ignores), set `#define DEBUG_TIMING 1`.
- `CONF_THRESHOLD` (default 0.50) is the minimum box confidence that counts as a detection.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERR: Failed to initialize camera` | Check the shield seating and the camera ribbon. Power-cycle the board. |
| TFLite arena allocation failure | Add `-DEI_CLASSIFIER_ALLOCATION_STATIC` to `boards.local.txt`. The sketch header explains how. |
| Only `N,` lines | Lighting, framing, or the subject isn't visible to the model. Lower `CONF_THRESHOLD` with care and re-check with `gateway.py --stats`. |
| Gateway can't open the port | Close the Arduino Serial Monitor, because only one program can hold the port. Check the COM port / `/dev/ttyACM*` name. |

## Retraining the model

The model was trained in Edge Impulse: project ID `1061466`, FOMO, 96×96 greyscale input (squash resize), one class `pet`, a TFLite arena of about 181 KB, exported with Edge Impulse Studio 1.94.5. To retrain it, export a new **Arduino library** from Edge Impulse and replace `edge-impulse-lib/CodeAbbas-project-1_inferencing/`. The header name the sketch includes (`CodeAbbas-project-1_inferencing.h`) follows the Edge Impulse project name. If you rename the project, update the `#include` line too.
