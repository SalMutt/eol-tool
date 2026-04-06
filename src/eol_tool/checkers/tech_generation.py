"""Technology generation checker using local pattern matching rules.

Determines EOL status by identifying the technology generation of hardware
from model numbers and part number patterns. No HTTP calls — all matching
is local.
"""

import re
from datetime import date, datetime

from ..checker import BaseChecker
from ..models import EOLReason, EOLResult, EOLStatus, HardwareModel, RiskCategory


class TechGenerationChecker(BaseChecker):
    """Determines EOL status by technology generation from model/part numbers."""

    manufacturer_name = "__techgen__"
    rate_limit = 100
    priority = 60
    base_url = ""

    async def check(self, model: HardwareModel) -> EOLResult:
        result = self._match_rules(model)
        if result:
            return result
        return EOLResult(
            model=model,
            status=EOLStatus.NOT_FOUND,
            checked_at=datetime.now(),
            source_name="tech-generation-rules",
            confidence=0,
            notes="no-matching-tech-generation-rule",
        )

    def _match_rules(self, model: HardwareModel) -> EOLResult | None:
        result = self._check_vendor_acquired(model)
        if result:
            return result

        for check_fn in [
            self._check_memory,
            self._check_cpu,
            self._check_storage,
            self._check_network,
            self._check_gpu,
            self._check_cooling,
            self._check_server_platforms,
            self._check_raid_controllers,
            self._check_hpe,
        ]:
            result = check_fn(model)
            if result:
                return result

        return None

    def _make_result(
        self,
        model: HardwareModel,
        status: EOLStatus,
        risk: RiskCategory,
        notes: str,
        eol_reason: EOLReason = EOLReason.TECHNOLOGY_GENERATION,
        eol_date: date | None = None,
        date_source: str = "none",
    ) -> EOLResult:
        return EOLResult(
            model=model,
            status=status,
            checked_at=datetime.now(),
            source_name="tech-generation-rules",
            confidence=65,
            notes=notes,
            eol_reason=eol_reason,
            risk_category=risk,
            eol_date=eol_date,
            date_source=date_source,
        )

    # ------------------------------------------------------------------
    # Vendor-acquired rules
    # ------------------------------------------------------------------

    def _check_vendor_acquired(self, model: HardwareModel) -> EOLResult | None:
        mfr = model.manufacturer.lower()
        if mfr == "brocade":
            return self._make_result(
                model,
                EOLStatus.EOL,
                RiskCategory.SECURITY,
                "Brocade acquired by Broadcom — all legacy products EOL",
                eol_reason=EOLReason.VENDOR_ACQUIRED,
                eol_date=date(2017, 11, 17),
                date_source="community_database",
            )
        if mfr == "evga":
            return self._make_result(
                model,
                EOLStatus.EOL,
                RiskCategory.PROCUREMENT,
                "EVGA exited GPU business 2022",
                eol_reason=EOLReason.VENDOR_ACQUIRED,
                eol_date=date(2022, 9, 16),
                date_source="community_database",
            )
        if mfr == "hitachi":
            return self._make_result(
                model,
                EOLStatus.EOL,
                RiskCategory.PROCUREMENT,
                "hitachi-gst-acquired-by-western-digital-2012",
                eol_reason=EOLReason.VENDOR_ACQUIRED,
                eol_date=date(2012, 3, 8),
                date_source="community_database",
            )
        if mfr == "ocz":
            return self._make_result(
                model,
                EOLStatus.EOL,
                RiskCategory.PROCUREMENT,
                "OCZ acquired by Toshiba 2014",
                eol_reason=EOLReason.VENDOR_ACQUIRED,
                eol_date=date(2014, 1, 21),
                date_source="community_database",
            )
        return None

    # ------------------------------------------------------------------
    # Memory (DDR generation)
    # ------------------------------------------------------------------

    _DDR5_PREFIXES = ["HMCG", "M321", "KSM48", "KSM56", "KVR48", "KVR56", "CP2K"]
    _DDR4_PREFIXES = [
        "HMA", "HMAA",
        "M393A", "M391A", "M386A",
        "MTA18ADF", "MTA36ASF",
        "KSM24", "KSM26", "KSM29", "KSM32",
        "KVR21", "KVR24", "KVR26",
        "CT16G4RFD4", "CT32G4RFD4",
    ]
    _DDR3_PREFIXES = [
        "HMT",
        "M393B",
        "MT36KSF", "MT18KSF",
        "KVR13", "KVR16",
    ]

    def _check_memory(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()
        cat = model.category.lower()
        mfr = model.manufacturer.lower()
        is_memory_cat = cat in ("memory", "ram", "dimm")

        # Corsair DDR5 memory
        if mfr == "corsair" and ("DDR5" in m or m.startswith("CMK")):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "Corsair DDR5 memory — current generation",
            )

        # DDR5 (check first — most current)
        if (
            any(m.startswith(p) for p in self._DDR5_PREFIXES)
            or "DDR5" in m
            or (is_memory_cat and re.search(r"(?<!\d)(?:4800|5600)(?!\d)", m))
        ):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "DDR5 memory — current generation",
            )

        # DDR4
        if (
            any(m.startswith(p) for p in self._DDR4_PREFIXES)
            or "DDR4" in m
            or (is_memory_cat and re.search(r"(?<!\d)(?:2133|2400|2666|2933|3200)(?!\d)", m))
        ):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                "DDR4 memory — current but aging generation",
            )

        # DDR3 (check last — oldest)
        if (
            any(m.startswith(p) for p in self._DDR3_PREFIXES)
            or "DDR3" in m or "PC3" in m
            or (is_memory_cat and re.search(r"(?<!\d)(?:1333|1600)(?!\d)", m))
        ):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "DDR3 memory — end of life generation",
            )

        # Kingston server memory — KTH/KTD with DDR generation encoding
        if mfr == "kingston" and (m.startswith("KTH") or m.startswith("KTD")):
            if re.search(r"(?:PL|PE)3", m):
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Kingston DDR3 server memory — end of life generation",
                )

        return None

    # ------------------------------------------------------------------
    # CPU (processor generation)
    # ------------------------------------------------------------------

    def _check_cpu(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()

        # Intel Xeon E3 with version suffix
        e3_match = re.search(r"E3-1\d{3}\s*V(\d)", m)
        if e3_match:
            v = int(e3_match.group(1))
            if v == 3:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.SUPPORT,
                    "Intel Xeon E3 v3 — end of life",
                )
            if v == 5:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                    "Intel Xeon E3 v5 — EOL, still gets microcode",
                )
            if v == 6:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                    "Intel Xeon E3 v6 — end of life",
                )

        # Intel Xeon E5 with version suffix
        e5_v_match = re.search(r"E5-\d{4}\s*V(\d)", m)
        if e5_v_match:
            v = int(e5_v_match.group(1))
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.SUPPORT,
                f"Intel Xeon E5 v{v} — end of life",
            )

        # Intel Xeon E5 without version suffix → v1
        if re.search(r"E5-\d{4}", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.SUPPORT,
                "Intel Xeon E5 v1 — end of life",
            )

        # Intel Xeon E-2100 series (Coffee Lake)
        if re.search(r"E-21\d{2}G?", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                "Intel Xeon E-2100 series — active",
            )

        # Intel Xeon E-2200 series (Coffee Lake Refresh)
        if re.search(r"E-22\d{2}G?", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                "Intel Xeon E-2200 series — active",
            )

        # Intel Xeon E-2300 series (Rocket Lake)
        if re.search(r"E-23\d{2}G?", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "Intel Xeon E-2300 series — active",
            )

        # Intel Xeon E-2400 series (Raptor Lake)
        if re.search(r"E-24\d{2}G?", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "Intel Xeon E-2400 series — active",
            )

        # Intel Xeon Scalable (require Intel context)
        mfr_upper = model.manufacturer.upper()
        has_intel_context = (
            mfr_upper == "INTEL"
            or "XEON" in m
            or any(kw in m for kw in ["GOLD", "SILVER", "PLATINUM", "BRONZE"])
        )
        if has_intel_context:
            # Gen 1/2: [12] for second digit avoids SSD model conflicts (S3500, P4510)
            scalable_match = re.search(r"(?<!\d)([3-8][12]\d{2})(?!\d)", m)
            if scalable_match:
                gen = int(scalable_match.group(1)[1])
                if gen == 1:
                    return self._make_result(
                        model, EOLStatus.EOL, RiskCategory.SUPPORT,
                        "Intel Xeon Scalable 1st gen (Skylake) — end of life",
                    )
                if gen == 2:
                    return self._make_result(
                        model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                        "Intel Xeon Scalable 2nd gen (Cascade Lake) — end of life",
                    )

            # Gen 3/4: broader second-digit range needs XEON/tier keyword or cpu category
            # to avoid false matches on SSD models like P4510, S3500
            has_xeon_kw = "XEON" in m or any(
                kw in m for kw in ["GOLD", "SILVER", "PLATINUM", "BRONZE"]
            )
            if has_xeon_kw or model.category.lower() in ("cpu", "processor"):
                scalable_34 = re.search(r"(?<!\d)([4-8][3-5]\d{2})(?!\d)", m)
                if scalable_34:
                    gen = int(scalable_34.group(1)[1])
                    if gen == 3:
                        return self._make_result(
                            model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                            "Intel Xeon Scalable 3rd gen (Ice Lake) — active",
                        )
                    if gen in (4, 5):
                        return self._make_result(
                            model, EOLStatus.ACTIVE, RiskCategory.NONE,
                            "Intel Xeon Scalable 4th gen (Sapphire Rapids) — active",
                        )

        # AMD EPYC
        epyc_match = re.search(r"EPYC\s*(\d)(\d{2})(\d)", m)
        if epyc_match:
            series = int(epyc_match.group(1))
            last = int(epyc_match.group(3))
            if series == 7 and last == 1:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.SUPPORT,
                    "AMD EPYC 7001 Naples — end of life",
                )
            if series == 7 and last == 2:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                    "AMD EPYC 7002 Rome — end of life",
                )
            if series == 7 and last == 3:
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                    "AMD EPYC 7003 Milan — active",
                )
            if series == 9 and last == 4:
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.NONE,
                    "AMD EPYC 9004 Genoa — active",
                )
            if series == 4 and last in (4, 5):
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.NONE,
                    "AMD EPYC 4004 Siena — active",
                )

        return None

    # ------------------------------------------------------------------
    # Storage (SSD generation)
    # ------------------------------------------------------------------

    _INTEL_SSD_EOL = [
        "S3500", "S3510", "S3520", "S35",
        "P3500", "P3520", "P3600",
        "P4500", "P4510", "P4511", "P4600",
        "S4510", "S4610",
    ]
    _MICRON_ACTIVE = ["5400", "7300", "7400", "7450", "7500", "9300", "9400"]

    def _check_storage(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()
        mfr = model.manufacturer.lower()

        # Intel SSDs — EOL
        for tag in self._INTEL_SSD_EOL:
            if tag in m:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    f"Intel SSD {tag} — end of life",
                )

        # Intel consumer/datacenter SSDs — category-gated
        cat = model.category.lower()
        if cat in ("ssd", "storage", "drive"):
            if "660P" in m:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Intel 660P — QLC NVMe, discontinued",
                )
            if "760P" in m:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Intel 760P — consumer NVMe, discontinued",
                )
            if re.search(r"(?<!X)540(?!\d)", m):
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Intel 540 series — consumer SATA, discontinued",
                )
            if re.search(r"(?<!X)520(?!\d)", m):
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Intel 520 series — consumer SATA, discontinued",
                )

        # Intel RAID expander
        if "RES2SV240" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Intel RES2SV240 — SAS expander, end of life",
            )

        # Samsung consumer SSDs
        if mfr == "samsung" or "SAMSUNG" in m:
            if re.search(r"\b8[45]0\b", m):
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Samsung 840/850 series — end of life",
                )
            if re.search(r"\b8[67]0\b", m):
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                    "Samsung 860/870 series — active",
                )
            if re.search(r"\b9[79]0\b", m):
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.NONE,
                    "Samsung 970/990 series — active",
                )

        # Samsung enterprise SSDs
        if re.search(r"PM863|PM883", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Samsung PM863/PM883 — end of life",
            )
        if re.search(r"PM893|PM9A3", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "Samsung PM893/PM9A3 — active",
            )

        # Micron SSDs
        if mfr == "micron" or "MICRON" in m:
            if re.search(r"\b5100\b", m):
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Micron 5100 — end of life",
                )
            if re.search(r"\b5210\b", m):
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "Micron 5210 — end of life",
                )
            for tag in self._MICRON_ACTIVE:
                if tag in m:
                    return self._make_result(
                        model, EOLStatus.ACTIVE, RiskCategory.NONE,
                        f"Micron {tag} — active",
                    )

        # Kingston SSDs — modern
        if mfr == "kingston":
            for prefix in ["SA400", "A2000", "NV1", "NV2", "DC"]:
                if m.startswith(prefix):
                    return self._make_result(
                        model, EOLStatus.ACTIVE, RiskCategory.NONE,
                        f"Kingston {prefix} storage — active",
                    )

        return None

    # ------------------------------------------------------------------
    # Network adapters
    # ------------------------------------------------------------------

    def _check_network(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()

        # Intel generic / optics — too generic to determine
        if "1GBE ETHERNET" in m:
            return self._make_result(
                model, EOLStatus.NOT_FOUND, RiskCategory.NONE,
                "Intel 1GbE Ethernet — too generic to determine EOL",
            )
        if "SFP-10GSR-85" in m:
            return self._make_result(
                model, EOLStatus.NOT_FOUND, RiskCategory.NONE,
                "Generic SFP+ optic — too generic to determine EOL",
            )

        # Intel NICs — EOL
        if "X520" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Intel X520 NIC — discontinued ~2018",
            )
        if "X540" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Intel X540 NIC — discontinued ~2019",
            )

        # Intel NICs — active
        if "I350" in m:
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                "Intel I350 NIC — still widely available",
            )
        for tag in ["X550", "X710", "X722"]:
            if tag in m:
                return self._make_result(
                    model, EOLStatus.ACTIVE, RiskCategory.NONE,
                    f"Intel {tag} NIC — current generation",
                )

        # Mellanox ConnectX-2/3 — EOL
        mellanox_eol = ["CX312A", "MNPA19", "MNPH29"]
        if any(p in m for p in mellanox_eol) or re.search(r"CONNECT-?X-?[23]", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Mellanox ConnectX-2/3 — end of life",
            )

        # Mellanox ConnectX-4/5 — active
        mellanox_active = ["CX4121A", "CX456A"]
        if any(p in m for p in mellanox_active) or re.search(r"CONNECT-?X-?[45]", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "Mellanox ConnectX-4/5 — active",
            )

        # IBM/Lenovo RackSwitch
        if model.manufacturer.lower() == "ibm" and m.startswith("4273"):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.SUPPORT,
                "IBM/Lenovo RackSwitch G8272 — discontinued",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            )

        return None

    # ------------------------------------------------------------------
    # GPU
    # ------------------------------------------------------------------

    def _check_gpu(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()

        # NVIDIA Tesla K80 (Kepler)
        if "K80" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.SUPPORT,
                "NVIDIA Tesla K80 (Kepler) — end of life",
            )

        # NVIDIA GeForce 210
        if re.search(r"GEFORCE\s*210", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "NVIDIA GeForce 210 — end of life",
            )

        # NVIDIA GeForce GTX 1080 Ti
        if re.search(r"GTX\s*1080\s*TI", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                "NVIDIA GeForce GTX 1080 Ti — end of life",
            )

        # Zotac GPUs (Pascal era)
        if model.manufacturer.lower() == "zotac" and m.startswith("ZT-P"):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "Zotac GPU (Pascal) — end of life",
            )

        # PNY GeForce GPUs (Pascal era)
        if m.startswith("VCG") and "1080" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "PNY GTX 1080 Ti (Pascal) — end of life",
            )

        # NVIDIA GP100 / Quadro GP100 (Pascal era)
        if "GP100" in m or "VCQGP100" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "NVIDIA Tesla/Quadro GP100 — end of life",
            )

        # NVIDIA Quadro K1200 (Maxwell era)
        if re.search(r"\bK1200\b|VCQK1200", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                "NVIDIA Quadro K1200 (Maxwell) — end of life",
            )

        # PNY/NVIDIA Quadro RTX 4000 (Turing)
        if m.startswith("VCQRTX4000"):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                "NVIDIA Quadro RTX 4000 (Turing) — end of life",
            )

        # PNY/NVIDIA Quadro P-series (Pascal)
        if m.startswith("VCQP"):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "NVIDIA Quadro P-series (Pascal) — end of life",
            )

        # NVIDIA Tesla/Quadro P-series
        if re.search(r"\bP1000\b|\bP2200\b", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.INFORMATIONAL,
                "NVIDIA Tesla/Quadro P-series — end of life",
            )

        # NVIDIA RTX 5000 workstation (active)
        if re.search(r"\bRTX\s*5000\b|VCQRTX5000", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "NVIDIA RTX 5000 workstation — active",
            )

        # NVIDIA RTX A-series (active)
        if re.search(r"RTXA|\bA4000\b|\bA5000\b|\bA6000\b", m):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "NVIDIA RTX A-series — active",
            )
        # A2 checked separately (short pattern needs word boundary)
        if re.search(r"\bA2\b", m) and (
            model.manufacturer.upper() == "NVIDIA"
            or "RTX" in m
            or model.category.lower() in ("gpu", "graphics", "video")
        ):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "NVIDIA RTX A-series — active",
            )

        return None

    # ------------------------------------------------------------------
    # Cooling
    # ------------------------------------------------------------------

    def _check_cooling(self, model: HardwareModel) -> EOLResult | None:
        if model.manufacturer.lower() == "dynatron":
            return self._make_result(
                model, EOLStatus.UNKNOWN, RiskCategory.NONE,
                "heatsink-lifecycle-follows-cpu-socket",
            )
        return None

    # ------------------------------------------------------------------
    # Server platforms (ASUS, ASRock)
    # ------------------------------------------------------------------

    def _check_server_platforms(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()
        mfr = model.manufacturer.lower()

        # ASUS server barebones — Intel/AMD platform generations
        if mfr == "asus" and m.startswith("RS"):
            gen_match = re.search(r"-E(\d+)", m)
            if gen_match:
                gen = int(gen_match.group(1))
                if gen <= 9:
                    return self._make_result(
                        model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                        f"ASUS server E{gen} platform — end of life",
                    )
                if gen == 10:
                    return self._make_result(
                        model, EOLStatus.ACTIVE, RiskCategory.INFORMATIONAL,
                        f"ASUS server E{gen} platform — active",
                    )
                if gen >= 11:
                    return self._make_result(
                        model, EOLStatus.ACTIVE, RiskCategory.NONE,
                        f"ASUS server E{gen} platform — active",
                    )

        # ASRock Rack — AMD EPYC 8004 Siena platform
        if mfr == "asrock" and m.startswith("S80"):
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "ASRock Rack EPYC 8004 Siena platform — active",
            )

        return None

    # ------------------------------------------------------------------
    # RAID controllers (IBM ServeRAID, Adaptec)
    # ------------------------------------------------------------------

    def _check_raid_controllers(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()
        mfr = model.manufacturer.lower()

        # IBM ServeRAID controllers and accessories
        if mfr == "ibm":
            if "M50" in m or "M52" in m:
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.SUPPORT,
                    "IBM ServeRAID controller — discontinued",
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                )
            if m == "46C9111":
                return self._make_result(
                    model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                    "IBM ServeRAID battery pack — discontinued",
                    eol_reason=EOLReason.PRODUCT_DISCONTINUED,
                )

        # Adaptec RAID controllers
        if mfr == "adaptec" and "ASR-" in m:
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "adaptec-raid-discontinued-microsemi-microchip-acquisition",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            )

        return None

    # ------------------------------------------------------------------
    # HPE legacy components
    # ------------------------------------------------------------------

    def _check_hpe(self, model: HardwareModel) -> EOLResult | None:
        m = model.model.upper()
        if model.manufacturer.lower() != "hpe":
            return None

        # HPE optics — active
        if "SFP" in m or "QSFP" in m:
            return self._make_result(
                model, EOLStatus.ACTIVE, RiskCategory.NONE,
                "HPE branded optic — active",
            )

        # HPE legacy drives — model contains MB and ends with digits
        if "MB" in m and re.search(r"\d$", m):
            return self._make_result(
                model, EOLStatus.EOL, RiskCategory.PROCUREMENT,
                "HPE legacy drive — end of life",
                eol_reason=EOLReason.PRODUCT_DISCONTINUED,
            )

        return None
