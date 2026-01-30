# Native Dependencies Detection

Scan `requirements.txt`, `pyproject.toml`, or `uv.lock` for these packages.
If found, uncomment the corresponding line in Dockerfile builder stage.

## Detection Table

| Package | Requires | Dockerfile Line |
|---------|----------|-----------------|
| `psycopg2`, `psycopg2-binary` | PostgreSQL client | `libpq-dev` |
| `asyncpg` | PostgreSQL client | `libpq-dev` |
| `mysqlclient` | MySQL client | `default-libmysqlclient-dev` |
| `cryptography` | SSL + Rust | `libssl-dev libffi-dev cargo rustc` |
| `bcrypt` | Build tools | `build-essential` |
| `pillow`, `PIL` | Image libs | `libjpeg-dev zlib1g-dev` |
| `numpy`, `scipy` | BLAS/LAPACK | `libopenblas-dev` |
| `pandas` | Build tools | `build-essential` |
| `lxml` | XML libs | `libxml2-dev libxslt-dev` |
| `cffi` | FFI | `libffi-dev` |
| `pyyaml` | YAML | `libyaml-dev` |
| `greenlet` | Build tools | `build-essential` |

## Auto-Generate RUN Command

```dockerfile
# Generated based on detected dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \           # psycopg2, asyncpg
    libssl-dev \          # cryptography
    libffi-dev \          # cryptography, cffi
    && rm -rf /var/lib/apt/lists/*
```

## Detection Logic

```python
# Pseudocode for agent
NATIVE_DEPS_MAP = {
    "psycopg2": ["libpq-dev"],
    "asyncpg": ["libpq-dev"],
    "cryptography": ["libssl-dev", "libffi-dev", "cargo", "rustc"],
    "pillow": ["libjpeg-dev", "zlib1g-dev"],
    # ... etc
}

def detect_native_deps(requirements: list[str]) -> set[str]:
    apt_packages = set()
    for req in requirements:
        pkg_name = req.split("==")[0].split(">=")[0].lower()
        if pkg_name in NATIVE_DEPS_MAP:
            apt_packages.update(NATIVE_DEPS_MAP[pkg_name])
    return apt_packages
```

## ML/AI Packages (Heavy)

These require significant build dependencies:

| Package | Size Impact | Consider |
|---------|-------------|----------|
| `torch`, `tensorflow` | 2-5GB | Use official GPU images instead |
| `opencv-python` | 500MB+ | Use `opencv-python-headless` |
| `scikit-learn` | 200MB+ | Pre-build in CI, cache layer |

For ML workloads, consider:
- NVIDIA CUDA base images
- Pre-built wheels from PyPI
- Multi-stage build with heavy deps in builder only
