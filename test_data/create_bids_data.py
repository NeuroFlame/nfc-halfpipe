"""
Generate HALFpipe CI-style BIDS test datasets for test_data/siteN/.

Both BOLD and T1w start as 1×1×1(×1) zeros; NIfTI headers are binary-patched
to declare realistic scan dimensions so that HALFpipe/fMRIPrep can build the
Nipype workflow graph (workflow construction reads shape from the header).

BOLD patch: dim=[4,80,80,37,200], 3mm×3mm×3.3mm, TR=2s
T1w  patch: dim=[3,182,218,182], 1mm isotropic (MNI152 FOV), LAS orientation

nibabel 5.x overrides dim/pixdim to match the actual numpy array shape during
save. This script works around that by binary-patching the gzipped NIfTI header.

NIfTI-1 header offsets patched:
  40  dim[0:8]       8×int16
  76  pixdim[0:8]    8×float32
 123  xyzt_units     uint8
 252  qform_code     int16
 254  sform_code     int16
 256  quatern_b/c/d  3×float32
 268  qoffset_x/y/z  3×float32
 280  srow_x[0:4]    4×float32
 296  srow_y[0:4]    4×float32
 312  srow_z[0:4]    4×float32

Run from project root:
    python3 test_data/create_bids_data.py
"""
import gzip
import json
import shutil
import struct
import tempfile
from pathlib import Path

import nibabel as nib
import numpy as np


HERE = Path(__file__).parent

SITES = {
    "site1": 12,
    "site2": 9,
    "site3": 15,
}

BOLD_SIDECAR = {
    "EchoTime": 0.02762,
    "RepetitionTime": 0.75,
}

DATASET_DESC = {
    "Name": "nfc-halfpipe test dataset",
    "BIDSVersion": "1.2.0",
}


def _patch_bold_header(path: Path) -> None:
    with gzip.open(str(path), "rb") as f:
        data = bytearray(f.read())
    struct.pack_into("<8h", data, 40, 4, 80, 80, 37, 200, 1, 1, 1)
    struct.pack_into("<8f", data, 76, -1.0, 3.0, 3.0, 3.3, 2.0, 0.0, 0.0, 0.0)
    struct.pack_into("<B",  data, 123, 10)
    struct.pack_into("<hh", data, 252, 1, 1)
    struct.pack_into("<fff", data, 256, -0.016865054, 0.98754567, 0.15574434)
    struct.pack_into("<fff", data, 268, 124.18631, -77.02284, -72.6236)
    struct.pack_into("<4f", data, 280, -2.9970164, -0.11356224, -0.077747233, 124.18631)
    struct.pack_into("<4f", data, 296, -0.08629788,  2.8527555, -1.0167344, -77.02284)
    struct.pack_into("<4f", data, 312, -0.10219894,  0.9213517,  3.1385038, -72.6236)
    with gzip.open(str(path), "wb") as f:
        f.write(data)


def _make_bold(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = nib.Nifti1Image(np.zeros((1, 1, 1, 1), dtype=np.float32), affine=np.eye(4))
    with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as fh:
        tmp = fh.name
    nib.save(img, tmp)
    shutil.move(tmp, str(path))
    _patch_bold_header(path)
    sidecar = path.parent / path.name.replace(".nii.gz", ".json")
    sidecar.write_text(json.dumps(BOLD_SIDECAR, indent=4))


def _patch_anat_header(path: Path) -> None:
    # Declare a 182×218×182 1mm isotropic MNI152-sized T1w (LAS orientation).
    # Actual compressed data remains 1×1×1 zeros; only the header is patched.
    with gzip.open(str(path), "rb") as f:
        data = bytearray(f.read())
    struct.pack_into("<8h", data, 40, 3, 182, 218, 182, 1, 1, 1, 1)
    struct.pack_into("<8f", data, 76, 1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0)
    struct.pack_into("<B",  data, 123, 10)
    struct.pack_into("<hh", data, 252, 1, 1)
    struct.pack_into("<fff", data, 256, 0.0, 0.0, 0.0)
    struct.pack_into("<fff", data, 268, -91.0, -126.0, -72.0)
    struct.pack_into("<4f", data, 280, -1.0, 0.0, 0.0, 91.0)
    struct.pack_into("<4f", data, 296,  0.0, 1.0, 0.0, -126.0)
    struct.pack_into("<4f", data, 312,  0.0, 0.0, 1.0, -72.0)
    with gzip.open(str(path), "wb") as f:
        f.write(data)


def _make_anat(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = nib.Nifti1Image(np.zeros((1, 1, 1), dtype=np.float32), affine=np.eye(4))
    with tempfile.NamedTemporaryFile(suffix=".nii.gz", delete=False) as fh:
        tmp = fh.name
    nib.save(img, tmp)
    shutil.move(tmp, str(path))
    _patch_anat_header(path)


def rebuild_site(site_name: str, n_subjects: int) -> None:
    # The site directory IS the BIDS root — matching how NeuroFLAME delivers
    # DATA_DIR to the computation (the directory the user points to in the UI).
    bids_dir = HERE / site_name
    print(f"Building {bids_dir} ({n_subjects} subjects) ...")

    for item in bids_dir.iterdir():
        if item.is_dir() and item.name.startswith("sub-"):
            shutil.rmtree(item)

    for fname in ("participants.json", "README"):
        p = bids_dir / fname
        if p.exists():
            p.unlink()

    (bids_dir / "dataset_description.json").write_text(json.dumps(DATASET_DESC, indent=4))

    subject_ids = [f"{i:04d}" for i in range(1, n_subjects + 1)]
    for sid in subject_ids:
        tag = f"sub-{sid}"
        _make_bold(bids_dir / tag / "func" / f"{tag}_task-rest_bold.nii.gz")
        _make_anat(bids_dir / tag / "anat"  / f"{tag}_T1w.nii.gz")
        print(f"  {tag}")

    lines = ["participant_id\tsex\tage"] + [f"sub-{sid}\tn/a\tn/a" for sid in subject_ids]
    (bids_dir / "participants.tsv").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    for site_name, n_subjects in SITES.items():
        rebuild_site(site_name, n_subjects)
    print("\nDone.")
