"""Tests for model string normalizer."""

from eol_tool.normalizer import normalize_model


class TestNormalizeBasic:
    def test_uppercase(self):
        assert normalize_model("ex4300-48t") == "EX4300-48T"

    def test_strip_whitespace(self):
        assert normalize_model("  EX4300  ") == "EX4300"

    def test_empty_string(self):
        assert normalize_model("") == ""

    def test_strip_capacity_gb(self):
        assert normalize_model("32GB SM863a") == "SM863A"

    def test_strip_capacity_tb(self):
        assert normalize_model("1.92TB PM1643a") == "PM1643A"

    def test_strip_capacity_mb(self):
        assert normalize_model("960MB SomeModel") == "SOMEMODEL"

    def test_no_manufacturer(self):
        assert normalize_model("EX4300-48T", "") == "EX4300-48T"


class TestIntelNormalization:
    def test_e3_collapse_v(self):
        assert normalize_model("E3-1230 V5", "Intel") == "XEON E3-1230V5"

    def test_e3_collapse_v3(self):
        assert normalize_model("E3-1230 V3", "Intel") == "XEON E3-1230V3"

    def test_e5_collapse_v(self):
        assert normalize_model("E5-2680 V4", "Intel") == "XEON E5-2680V4"

    def test_reorder_silver(self):
        assert normalize_model("4110 SILVER XEON", "Intel") == "XEON SILVER 4110"

    def test_gold_suffix(self):
        assert normalize_model("6146 GOLD", "Intel") == "XEON GOLD 6146"

    def test_silver_suffix(self):
        assert normalize_model("4110 SILVER", "Intel") == "XEON SILVER 4110"

    def test_already_clean(self):
        assert normalize_model("XEON E3-1230V5", "Intel") == "XEON E3-1230V5"

    def test_strip_intel_prefix(self):
        assert normalize_model("INTEL E3-1230 V5", "Intel") == "XEON E3-1230V5"

    def test_case_insensitive_manufacturer(self):
        assert normalize_model("E3-1230 V5", "intel") == "XEON E3-1230V5"


class TestAMDNormalization:
    def test_strip_amd_prefix(self):
        assert normalize_model("AMD EPYC 7282", "AMD") == "EPYC 7282"

    def test_already_clean(self):
        assert normalize_model("EPYC 7282", "AMD") == "EPYC 7282"


class TestSeagateNormalization:
    def test_strip_ent(self):
        assert normalize_model("ST1000NM ENT", "Seagate") == "ST1000NM"

    def test_strip_dash_suffix(self):
        assert normalize_model("ST1000NM - M0009", "Seagate") == "ST1000NM"

    def test_strip_both(self):
        assert normalize_model("ST1000NM ENT - M0009", "Seagate") == "ST1000NM"


class TestSamsungNormalization:
    def test_strip_sam_prefix(self):
        assert normalize_model("SAM PM1643a", "Samsung") == "PM1643A"

    def test_already_clean(self):
        assert normalize_model("PM1643A", "Samsung") == "PM1643A"


class TestSupermicroNormalization:
    def test_strip_sm_prefix(self):
        assert normalize_model("SM X11DPH-T", "Supermicro") == "X11DPH-T"

    def test_already_clean(self):
        assert normalize_model("X11DPH-T", "Supermicro") == "X11DPH-T"


class TestCategoryConditionPrefixStripping:
    def test_strip_mainboard_new(self):
        assert normalize_model("MAINBOARD:NEW:AsRock X470D4U", "ASRock") == "X470D4U"

    def test_strip_ssd_drives_new_with_capacity(self):
        assert normalize_model("SSD DRIVES:NEW:960GB ADATA SU650", "ADATA") == "SU650"

    def test_strip_switches_used(self):
        assert normalize_model("SWITCHES:USED:EX4200-48P", "Juniper") == "EX4200-48P"

    def test_strip_optics_prefix(self):
        assert normalize_model("OPTICS:JNP-QSFP-4X10GE-LR", "Juniper") == "JNP-QSFP-4X10GE-LR"

    def test_strip_memory_used_capacity_colon(self):
        result = normalize_model("MEMORY:USED:8GB:MTA9ASF1G72AZ-2G3B1", "Micron")
        assert result == "MTA9ASF1G72AZ-2G3B1"

    def test_strip_server_barebone(self):
        assert normalize_model("SERVER BAREBONE:NEW:Some Model", "") == "SOME MODEL"

    def test_no_prefix_passthrough(self):
        assert normalize_model("EX4300-48T", "Juniper") == "EX4300-48T"


class TestCapacityColonSeparator:
    def test_capacity_colon(self):
        assert normalize_model("8GB:MTA9ASF1G72AZ", "Micron") == "MTA9ASF1G72AZ"

    def test_capacity_space(self):
        assert normalize_model("32GB MTA36ASF4G72PZ", "Micron") == "MTA36ASF4G72PZ"


class TestGenericBrandStripping:
    def test_strip_dell_prefix(self):
        assert normalize_model("DELL POWEREDGE R730XD", "Dell") == "POWEREDGE R730XD"

    def test_strip_cisco_prefix(self):
        result = normalize_model("CISCO 2500 WIRELESS CONTROLLER", "Cisco")
        assert result == "2500 WIRELESS CONTROLLER"

    def test_no_strip_when_no_manufacturer(self):
        assert normalize_model("DELL POWEREDGE R730XD", "") == "DELL POWEREDGE R730XD"


class TestASUSNormalization:
    def test_strip_asus_prefix(self):
        assert normalize_model("ASUS PRO WRX90E-SAGE SE", "ASUS") == "PRO WRX90E-SAGE SE"

    def test_strip_asu_sv_prefix(self):
        assert normalize_model("ASU SV RS300-E11-WOCPU012Z", "ASUS") == "RS300-E11-WOCPU012Z"

    def test_strip_asu_prefix(self):
        assert normalize_model("ASU RS700-E9-RS12", "ASUS") == "RS700-E9-RS12"

    def test_already_clean(self):
        assert normalize_model("RS520A-E12-RS24U", "ASUS") == "RS520A-E12-RS24U"


class TestJuniperNormalization:
    def test_just_uppercase(self):
        assert normalize_model("ex4300-48t", "Juniper") == "EX4300-48T"
