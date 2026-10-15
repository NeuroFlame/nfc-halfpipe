"""
Atlas parcel labels for FNC column naming.

Sources
-------
Schaefer200 : Schaefer et al. 2018, 200-parcel 17-network ordering,
              FSLMNI152 2 mm space.  Labels match the ordering of
              Schaefer2018_200Parcels_17Networks_order_FSLMNI152_2mm.nii.gz
              (parcels 1-100 = LH, 101-200 = RH).

NeuroMark1  : Du et al. 2020 NeuroMark 1.0, 53-IC 7-domain parcellation.
              IC order matches NeuroMark_1.0_parcellation.nii.gz volumes
              (4-D, volume index = IC index - 1).
"""

# ---------------------------------------------------------------------------
# Schaefer 200-parcel / 17-network labels
# (LH parcels 1-100, RH parcels 101-200 — same network structure per hemi)
# ---------------------------------------------------------------------------

_SCHAEFER200_LH = [
    # VisCent (1-7)
    "LH_VisCent_ExStr_1", "LH_VisCent_ExStr_2", "LH_VisCent_ExStr_3",
    "LH_VisCent_StriV_4", "LH_VisCent_StriV_5", "LH_VisCent_StriV_6",
    "LH_VisCent_StriV_7",
    # VisPeri (8-17)
    "LH_VisPeri_ExStr_8", "LH_VisPeri_ExStr_9", "LH_VisPeri_ExStr_10",
    "LH_VisPeri_ExStr_11", "LH_VisPeri_ExStr_12", "LH_VisPeri_ExStr_13",
    "LH_VisPeri_ExStr_14", "LH_VisPeri_ExStr_15", "LH_VisPeri_ExStr_16",
    "LH_VisPeri_ExStr_17",
    # SomMotA (18-26)
    "LH_SomMotA_1", "LH_SomMotA_2", "LH_SomMotA_3", "LH_SomMotA_4",
    "LH_SomMotA_5", "LH_SomMotA_6", "LH_SomMotA_7", "LH_SomMotA_8",
    "LH_SomMotA_9",
    # SomMotB (27-32)
    "LH_SomMotB_Cent_10", "LH_SomMotB_Cent_11", "LH_SomMotB_Cent_12",
    "LH_SomMotB_Cent_13", "LH_SomMotB_S2_14", "LH_SomMotB_S2_15",
    # DorsAttnA (33-40)
    "LH_DorsAttnA_TPC_1", "LH_DorsAttnA_TPC_2", "LH_DorsAttnA_TPC_3",
    "LH_DorsAttnA_PostC_4", "LH_DorsAttnA_PostC_5", "LH_DorsAttnA_PostC_6",
    "LH_DorsAttnA_PostC_7", "LH_DorsAttnA_PostC_8",
    # DorsAttnB (41-45)
    "LH_DorsAttnB_PostC_9", "LH_DorsAttnB_PostC_10", "LH_DorsAttnB_PostC_11",
    "LH_DorsAttnB_PostC_12", "LH_DorsAttnB_PostC_13",
    # SalVentAttnA (46-52)
    "LH_SalVentAttnA_Ins_1", "LH_SalVentAttnA_Ins_2", "LH_SalVentAttnA_Ins_3",
    "LH_SalVentAttnA_FrMed_4", "LH_SalVentAttnA_FrMed_5",
    "LH_SalVentAttnA_FrMed_6", "LH_SalVentAttnA_FrMed_7",
    # SalVentAttnB (53-58)
    "LH_SalVentAttnB_IPL_8", "LH_SalVentAttnB_IPL_9", "LH_SalVentAttnB_IPL_10",
    "LH_SalVentAttnB_PrC_11", "LH_SalVentAttnB_PrC_12", "LH_SalVentAttnB_PrC_13",
    # LimbicOFC (59-61)
    "LH_LimbicOFC_OFC_1", "LH_LimbicOFC_OFC_2", "LH_LimbicOFC_OFC_3",
    # LimbicTempPole (62-64)
    "LH_LimbicTempPole_TempPole_4", "LH_LimbicTempPole_TempPole_5",
    "LH_LimbicTempPole_TempPole_6",
    # ContA (65-71)
    "LH_ContA_IPL_1", "LH_ContA_IPL_2", "LH_ContA_PFCl_3", "LH_ContA_PFCl_4",
    "LH_ContA_PFCl_5", "LH_ContA_PFCl_6", "LH_ContA_PFCl_7",
    # ContB (72-75)
    "LH_ContB_IPL_8", "LH_ContB_IPL_9", "LH_ContB_PFClv_10", "LH_ContB_PFClv_11",
    # ContC (76-77)
    "LH_ContC_pCun_12", "LH_ContC_pCun_13",
    # DefaultA (78-84)
    "LH_DefaultA_pCunPCC_1", "LH_DefaultA_pCunPCC_2", "LH_DefaultA_pCunPCC_3",
    "LH_DefaultA_IPL_4", "LH_DefaultA_IPL_5", "LH_DefaultA_PFCm_6",
    "LH_DefaultA_PFCm_7",
    # DefaultB (85-90)
    "LH_DefaultB_Temp_8", "LH_DefaultB_Temp_9", "LH_DefaultB_PFCdPFCm_10",
    "LH_DefaultB_PFCdPFCm_11", "LH_DefaultB_PFCdPFCm_12", "LH_DefaultB_PFCdPFCm_13",
    # DefaultC (91-94)
    "LH_DefaultC_Rsp_14", "LH_DefaultC_Rsp_15", "LH_DefaultC_PFCv_16",
    "LH_DefaultC_PFCv_17",
    # TempPar (95-100)
    "LH_TempPar_1", "LH_TempPar_2", "LH_TempPar_3", "LH_TempPar_4",
    "LH_TempPar_5", "LH_TempPar_6",
]

_SCHAEFER200_RH = [lbl.replace("LH_", "RH_") for lbl in _SCHAEFER200_LH]

# 1-indexed dict: parcel index → label string
SCHAEFER200_LABELS: dict[int, str] = {
    i + 1: lbl for i, lbl in enumerate(_SCHAEFER200_LH + _SCHAEFER200_RH)
}

# ---------------------------------------------------------------------------
# NeuroMark 1.0 — 53 ICs across 7 functional domains
# (IC index 1-53 = volume index 0-52 in the 4-D NIfTI)
# ---------------------------------------------------------------------------

_NEUROMARK1_DOMAINS = [
    # (domain_abbrev, count)
    ("SC",  5),   # Subcortical       ICs  1-5
    ("AU",  3),   # Auditory          ICs  6-8
    ("SM",  7),   # Sensorimotor      ICs  9-15
    ("VI",  8),   # Visual            ICs 16-23
    ("CC", 12),   # Cognitive Control ICs 24-35
    ("DMN",13),   # Default Mode      ICs 36-48
    ("CB",  5),   # Cerebellar        ICs 49-53
]

NEUROMARK1_LABELS: dict[int, str] = {}
_ic = 1
for _domain, _count in _NEUROMARK1_DOMAINS:
    for _k in range(1, _count + 1):
        NEUROMARK1_LABELS[_ic] = f"{_domain}-{_k}"
        _ic += 1

# ---------------------------------------------------------------------------
# Lookup helper
# ---------------------------------------------------------------------------

_ATLAS_LABEL_TABLES: dict[str, dict[int, str]] = {
    "connectivity_atlas-Schaefer200": SCHAEFER200_LABELS,
    "neuromark_atlas-NeuroMark1":     NEUROMARK1_LABELS,
}


def parcel_label(atlas_key: str, one_indexed: int) -> str:
    """Return the human-readable label for a parcel, falling back to index."""
    table = _ATLAS_LABEL_TABLES.get(atlas_key)
    if table:
        return table.get(one_indexed, str(one_indexed))
    return str(one_indexed)


def column_label(atlas_key: str, i: int, j: int) -> str:
    """Return the FNC column name for parcel pair (i, j) both 1-indexed."""
    return f"{parcel_label(atlas_key, i)}_x_{parcel_label(atlas_key, j)}"
