"""Tests for manufacturer auto-detection from model names."""

from eol_tool.reader import _detect_manufacturer


class TestJuniperDetection:
    def test_juniper_switch_detection(self):
        assert _detect_manufacturer("EX4300-48T", "switch") == "Juniper"

    def test_juniper_chassis_detection(self):
        assert _detect_manufacturer("CHAS-BP3-MX480", "chassis") == "Juniper"

    def test_juniper_psu_detection(self):
        assert _detect_manufacturer("JPSU-650W-AC-AFI", "psu") == "Juniper"

    def test_juniper_qfx(self):
        assert _detect_manufacturer("QFX5100-48S", "switch") == "Juniper"

    def test_juniper_srx(self):
        assert _detect_manufacturer("SRX345", "firewall") == "Juniper"

    def test_juniper_mx(self):
        assert _detect_manufacturer("MX480", "router") == "Juniper"

    def test_juniper_fan_tray(self):
        assert _detect_manufacturer("FFANTRAY-MX480-HC", "fan") == "Juniper"

    def test_juniper_routing_engine(self):
        assert _detect_manufacturer("RE-S-1800X4-32G", "module") == "Juniper"

    def test_juniper_mpc(self):
        assert _detect_manufacturer("MPC7E-10G", "module") == "Juniper"

    def test_juniper_mic(self):
        assert _detect_manufacturer("MIC-3D-20GE-SFP", "module") == "Juniper"

    def test_juniper_pf(self):
        assert _detect_manufacturer("PF-24XGE-SFPP", "module") == "Juniper"


class TestSupermicroDetection:
    def test_supermicro_chassis_detection(self):
        assert _detect_manufacturer("CSE-113AC2-605WB", "chassis") == "Supermicro"

    def test_supermicro_x9(self):
        assert _detect_manufacturer("X9DRI-LN4F+", "mainboard") == "Supermicro"

    def test_supermicro_x10(self):
        assert _detect_manufacturer("X10SRL-F", "mainboard") == "Supermicro"

    def test_supermicro_x11(self):
        assert _detect_manufacturer("X11SPH-NCTPF", "mainboard") == "Supermicro"

    def test_supermicro_x12(self):
        assert _detect_manufacturer("X12SPO-NTF", "mainboard") == "Supermicro"

    def test_supermicro_x13(self):
        assert _detect_manufacturer("X13SEI-TF", "mainboard") == "Supermicro"

    def test_supermicro_h12(self):
        assert _detect_manufacturer("H12SSL-NT", "mainboard") == "Supermicro"

    def test_supermicro_h13(self):
        assert _detect_manufacturer("H13DSG-OM", "mainboard") == "Supermicro"

    def test_supermicro_aoc(self):
        assert _detect_manufacturer("AOC-S25G-M2S", "nic") == "Supermicro"

    def test_supermicro_rsc(self):
        assert _detect_manufacturer("RSC-R2UW-E8R", "riser") == "Supermicro"

    def test_supermicro_bpn(self):
        assert _detect_manufacturer("BPN-SAS3-826EL1", "backplane") == "Supermicro"

    def test_supermicro_snk(self):
        assert _detect_manufacturer("SNK-P0068APS4", "heatsink") == "Supermicro"

    def test_supermicro_pio(self):
        assert _detect_manufacturer("PIO-627TR-DTRF", "node") == "Supermicro"


class TestSeagateDetection:
    def test_seagate_drive_detection(self):
        assert _detect_manufacturer("ST1000NX0313", "hdd") == "Seagate"

    def test_seagate_exos(self):
        assert _detect_manufacturer("ST16000NM001G", "hdd") == "Seagate"

    def test_hgst_legacy(self):
        assert _detect_manufacturer("HGST HUS726T4TALA6L4", "hdd") == "Seagate"


class TestWDDetection:
    def test_wd_drive(self):
        assert _detect_manufacturer("WD4003FFBX", "hdd") == "WD"

    def test_wd_ultrastar(self):
        assert _detect_manufacturer("WUS4BA1A1DSP3X3", "ssd") == "WD"

    def test_wd_wustr(self):
        assert _detect_manufacturer("WUSTR6440ASS204", "ssd") == "WD"


class TestKingstonDetection:
    def test_kingston_memory_detection(self):
        assert _detect_manufacturer("KTD-PE424/32G", "memory") == "Kingston"

    def test_kingston_kvr(self):
        assert _detect_manufacturer("KVR26N19S8/8", "memory") == "Kingston"

    def test_kingston_ksm(self):
        assert _detect_manufacturer("KSM26RD4/32MEI", "memory") == "Kingston"

    def test_kingston_ktl(self):
        assert _detect_manufacturer("KTL-TS424/32G", "memory") == "Kingston"

    def test_kingston_k_series(self):
        assert _detect_manufacturer("K4A8G045WC", "memory") == "Kingston"


class TestMicronDetection:
    def test_micron_memory_detection(self):
        assert _detect_manufacturer("MTA36ASF4G72PZ", "memory") == "Micron"

    def test_micron_mem_dr(self):
        assert _detect_manufacturer("MEM-DR464L-CL03-ER32", "memory") == "Micron"


class TestSamsungDetection:
    def test_samsung_mz(self):
        assert _detect_manufacturer("MZ-76E500B", "ssd") == "Samsung"

    def test_samsung_pm(self):
        assert _detect_manufacturer("PM1643A", "ssd") == "Samsung"

    def test_samsung_sm(self):
        assert _detect_manufacturer("SM863A", "ssd") == "Samsung"


class TestIntelDetection:
    def test_intel_ssd_detection(self):
        assert _detect_manufacturer("SSDPE2KX040T8", "ssd") == "Intel"

    def test_intel_ssdsc(self):
        assert _detect_manufacturer("SSDSC2KB960G8", "ssd") == "Intel"

    def test_intel_dc_p(self):
        assert _detect_manufacturer("DC P4101", "ssd") == "Intel"

    def test_intel_d3_s(self):
        assert _detect_manufacturer("D3-S4510", "ssd") == "Intel"

    def test_intel_nic_detection(self):
        assert _detect_manufacturer("X520-DA2", "nic") == "Intel"

    def test_intel_x710(self):
        assert _detect_manufacturer("X710-BM2", "nic") == "Intel"

    def test_intel_e810(self):
        assert _detect_manufacturer("E810-XXVDA2", "nic") == "Intel"

    def test_intel_i350(self):
        assert _detect_manufacturer("I350-T4", "nic") == "Intel"


class TestDellDetection:
    def test_dell_server_detection(self):
        assert _detect_manufacturer("POWEREDGE R750", "server") == "Dell"

    def test_dell_r_series(self):
        assert _detect_manufacturer("R640", "server") == "Dell"

    def test_dell_r_series_lowercase(self):
        assert _detect_manufacturer("r750xa", "server") == "Dell"


class TestAMDDetection:
    def test_amd_gpu_detection(self):
        assert _detect_manufacturer("EPYC 7413", "cpu") == "AMD"

    def test_amd_ryzen(self):
        assert _detect_manufacturer("RYZEN 9 5950X", "cpu") == "AMD"

    def test_amd_radeon(self):
        assert _detect_manufacturer("RADEON PRO W6800", "gpu") == "AMD"

    def test_amd_mi(self):
        assert _detect_manufacturer("MI250X", "gpu") == "AMD"


class TestBroadcomDetection:
    def test_broadcom_bcm(self):
        assert _detect_manufacturer("BCM57412", "nic") == "Broadcom"

    def test_broadcom_n2(self):
        assert _detect_manufacturer("N2100G", "nic") == "Broadcom"


class TestNVIDIADetection:
    def test_nvidia_p_series(self):
        assert _detect_manufacturer("P2200", "gpu") == "NVIDIA"

    def test_nvidia_rtx(self):
        assert _detect_manufacturer("RTX A6000", "gpu") == "NVIDIA"

    def test_nvidia_t_series(self):
        assert _detect_manufacturer("T1000", "gpu") == "NVIDIA"

    def test_nvidia_a_series(self):
        assert _detect_manufacturer("A2000", "gpu") == "NVIDIA"


class TestCategorySpecificRules:
    def test_switch_ex_juniper(self):
        assert _detect_manufacturer("EX4300-48T", "switch") == "Juniper"

    def test_memory_mta_micron(self):
        assert _detect_manufacturer("MTA36ASF4G72PZ", "memory") == "Micron"

    def test_memory_kvr_kingston(self):
        assert _detect_manufacturer("KVR26N19S8/8", "memory") == "Kingston"


class TestEdgeCases:
    def test_does_not_override_existing(self):
        """_detect_manufacturer only returns a suggestion; caller must not override."""
        # The function always returns a result based on model, regardless of
        # existing manufacturer. The caller (read_models) handles the override logic.
        result = _detect_manufacturer("EX4300-48T", "switch")
        assert result == "Juniper"

    def test_unknown_model_returns_none(self):
        assert _detect_manufacturer("FOOBARBAZ123", "widget") is None

    def test_case_insensitive(self):
        assert _detect_manufacturer("ex4300-48t", "switch") == "Juniper"
        assert _detect_manufacturer("ssdpe2kx040t8", "ssd") == "Intel"
        assert _detect_manufacturer("epyc 7413", "cpu") == "AMD"
