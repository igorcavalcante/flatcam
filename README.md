FlatCAM: 2D Computer-Aided PCB Manufacturing
============================================

This project is a **fork** created to run FlatCAM with modern dependencies on Linux, specifically migrating the graphical interface from PyQt4 to **PyQt5** and resolving incompatibilities with current libraries. The dependency adjustments and porting were performed with the assistance of AI.

The original repository developed by Juan Pablo Caram can be found at:
- [https://bitbucket.org/jpcgt/flatcam](https://bitbucket.org/jpcgt/flatcam)

---

## How to Install and Run on Linux

### 1. Prerequisites
Make sure you have Python 3 installed on your system, along with system tools required for compiling C-based dependencies (such as `rtree` and `shapely`).

On Ubuntu/Debian, you can install the system packages using:
```bash
sudo apt install python3-pip libspatialindex-dev
```

### 2. Install Python Dependencies
Install the required python packages listed in `requirements.txt` using `pip`:
```bash
pip install -r requirements.txt
```

### 3. How to Run FlatCAM
After installing the dependencies, you can start the application by running the main script:
```bash
python3 flatcam
```
