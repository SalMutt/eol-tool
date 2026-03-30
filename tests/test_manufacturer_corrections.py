"""Tests for the manufacturer correction layer."""

from eol_tool.manufacturer_corrections import apply_manufacturer_corrections
from eol_tool.models import HardwareModel


def _hw(model: str, manufacturer: str, original_item: str = "") -> HardwareModel:
    return HardwareModel(
        model=model,
        manufacturer=manufacturer,
        category="other",
        original_item=original_item,
    )


class TestManufacturerCorrections:
    def test_arista_in_model(self):
        models = [_hw("7050QX-32", "Seagate", "SWITCHES:USED:Arista 7050QX-32")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Arista"

    def test_arista_in_original_item_only(self):
        models = [_hw("QSFP-100G-SR4", "Seagate", "OPTICS:NEW:Arista QSFP-100G-SR4")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Arista"

    def test_arista_uppercase(self):
        models = [_hw("40G QSFP+", "Seagate", "OPTICS:NEW:ARISTA 40G QSFP+")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Arista"

    def test_juniper_aif_sp_fxp(self):
        models = [_hw("AIF-SP-FXP-CORE-R10-F0KSTD-RNW", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_juniper_aif_tms_software(self):
        models = [_hw("AIF-TMS-SOFTWARE-FXP25G-STD-RNW", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_juniper_aif_sp_fxp_space(self):
        models = [_hw("SP-FXP-CORE_X0002_F10K-STD- RNW", "Seagate",
                       "NETWORK DEVICES:NEW:AIF SP-FXP-CORE_x0002_F10K-STD- RNW")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_ibm_46c9111(self):
        models = [_hw("46C9111 SERVERAID M5210 STO", "Seagate",
                       "RAID CARDS:NEW:IBM 46C9111 ServeRAID M5210 Sto")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "IBM"

    def test_ibm_serveraid_keyword(self):
        models = [_hw("SERVERAID-M5210", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "IBM"

    def test_supermicro_x10slh(self):
        models = [_hw("X10SLH-N6-ST031", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Supermicro"

    def test_no_correction_needed(self):
        models = [_hw("X470D4U", "ASRock")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "ASRock"

    def test_already_correct_arista(self):
        """No log if already correct."""
        models = [_hw("7050QX-32", "Arista", "SWITCHES:USED:Arista 7050QX-32")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Arista"

    def test_juniper_mx960(self):
        models = [_hw("MX960", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_juniper_pwr_mx960(self):
        models = [_hw("PWR-MX960-4100-AC-S", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_juniper_mic3_3d(self):
        models = [_hw("MIC3-3D-1X100GE-CFP2", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_juniper_jnp_qsfp(self):
        models = [_hw("JNP-QSFP-4X10GE-LR", "Supermicro")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Juniper"

    def test_pny_vcggtx1080(self):
        models = [_hw("VCGGTX1080T11PB-CG2", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "PNY"

    def test_toshiba_thnsnh(self):
        models = [_hw("THNSNH256GBST", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Toshiba"

    def test_toshiba_tos_thnsnh(self):
        models = [_hw("TOS THNSNH256GBST", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Toshiba"

    def test_asrock_s8016agm2nr(self):
        models = [_hw("S8016AGM2NR", "Seagate")]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "ASRock"

    def test_multiple_models(self):
        models = [
            _hw("7050QX-32", "Seagate", "SWITCHES:USED:Arista 7050QX-32"),
            _hw("AIF-SP-FXP-CORE", "Seagate"),
            _hw("X470D4U", "ASRock"),
        ]
        apply_manufacturer_corrections(models)
        assert models[0].manufacturer == "Arista"
        assert models[1].manufacturer == "Juniper"
        assert models[2].manufacturer == "ASRock"
