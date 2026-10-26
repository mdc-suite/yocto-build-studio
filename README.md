# Yocto Build Studio

Yocto Build Studio is a desktop application designed to simplify common Yocto Project workflows. It provides a graphical interface for managing build dependencies, synchronizing Xilinx repositories, importing Yocto layers, configuring build environments, and launching BitBake builds.

The goal is to make embedded Linux development more accessible and manageable without requiring every operation to be performed manually from the terminal.

## Project Structure

The repository is intended to follow a structure similar to the following:

```text
yocto-build-studio/
├── yocto_build_studio.py   # Main desktop application
├── meta-unica_ss.zip       # Custom layer
├── requirements.txt        # Python dependencies
├── README.md               # Project documentation
└── LICENSE                 # Project license
```

## Features

- **Desktop GUI** — A modern interface built with Python and CustomTkinter.
- **Host dependency management** — Check and install the packages required by the development environment.
- **Xilinx repository synchronization** — Synchronize the Xilinx Yocto repository for the selected release.
- **Layer management** — Import Yocto layers from ZIP archives or Git repositories.
- **Build configuration** — Manage the layers included in the Yocto build environment.
- **Board detection** — Identify supported Xilinx platform families, including Zynq-7000 and Zynq UltraScale+.
- **BitBake integration** — Launch builds for supported embedded Linux images.
- **Build output** — Display command output and progress information in the application.

## Supported Platforms

Yocto Build Studio is primarily intended for Linux-based development environments.

| Component | Target |
|---|---|
| Host operating system | Ubuntu 22.04 LTS |
| Programming language | Python 3 |
| GUI framework | CustomTkinter |
| Build system | Yocto Project / BitBake |
| Hardware platforms | Xilinx Zynq-7000 and Zynq UltraScale+ |
| Xilinx release | `rel-v2023.2` |


## Requirements

Before using Yocto Build Studio, make sure your system has:

- Ubuntu 22.04 LTS or a compatible Linux distribution.
- Python 3 and `pip`.
- Git.
- CustomTkinter and the Python dependencies required by the application.
- The host packages required by the selected Yocto release.
- Sufficient disk space for source repositories, build artifacts, and generated images.

Some operations may require administrator privileges, particularly when installing system packages.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/mdc-suite/yocto-build-studio.git
cd yocto-build-studio
```

### 2. Install Python dependencies

If the project provides a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 4. Launch the application

```bash
python3 yocto_build_studio.py
```

## Getting Started

A typical workflow with Yocto Build Studio looks like this:

1. **Check host dependencies** to verify that the development environment is ready.
2. **Synchronize the Xilinx repositories** for the desired release.
3. **Import the required Yocto layers** from ZIP archives or Git repositories.
4. **Configure the build layers** used by the selected build environment.
5. **Select or detect the target platform** supported by your configuration.
6. **Choose the target image** to build.
7. **Start the BitBake build** and monitor the output.
8. **Retrieve the generated artifacts** from the corresponding Yocto build directory.

## Supported Build Targets

Yocto Build Studio is intended to support workflows involving embedded Linux images and additional software stacks.

Potential build targets include:

- Minimal embedded Linux images.
- AXI DMA-related development configurations.
- Vitis AI-related configurations.
- K3s-related configurations.

**Important:** These targets require the appropriate metadata, recipes, machine configurations, and dependencies. Their availability depends on the layers installed and the configuration of the selected build environment.


