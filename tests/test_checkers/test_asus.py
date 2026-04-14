"""Tests for the ASUSChecker."""

import pytest

from eol_tool.checkers.asus import ASUSChecker
from eol_tool.models import EOLReason, EOLStatus, HardwareModel


@pytest.fixture
def checker():
    return ASUSChecker()


def _hw(model: str, category: str = "server-board") -> HardwareModel:
    return HardwareModel(model=model, manufacturer="ASUS", category=category)


class TestASUSBoardsEOL:
    async def test_z10pe_eol(self, checker):
        r = await checker.check(_hw("Z10PE-D16"))
        assert r.status == EOLStatus.EOL
        assert r.eol_reason == EOLReason.TECHNOLOGY_GENERATION

    async def test_z11pa_eol(self, checker):
        r = await checker.check(_hw("Z11PA-D8"))
        assert r.status == EOLStatus.EOL

    async def test_krpa_eol(self, checker):
        r = await checker.check(_hw("KRPA-U16"))
        assert r.status == EOLStatus.EOL
        assert "EPYC 7002" in r.notes


class TestASUSBoardsActive:
    async def test_z12pp_active(self, checker):
        r = await checker.check(_hw("Z12PP-D32"))
        assert r.status == EOLStatus.ACTIVE

    async def test_z13pa_active(self, checker):
        r = await checker.check(_hw("Z13PA-D32"))
        assert r.status == EOLStatus.ACTIVE

    async def test_krpg_active(self, checker):
        r = await checker.check(_hw("KRPG-U8"))
        assert r.status == EOLStatus.ACTIVE
        assert "EPYC 7003" in r.notes

    async def test_wrx90_active(self, checker):
        r = await checker.check(_hw("Pro WS WRX90E-SAGE"))
        assert r.status == EOLStatus.ACTIVE


class TestASUSSystemGenerations:
    async def test_e8_server_eol(self, checker):
        r = await checker.check(_hw("RS720-E8-RS24", category="server"))
        assert r.status == EOLStatus.EOL

    async def test_e9_server_eol(self, checker):
        r = await checker.check(_hw("RS700-E9-RS12", category="server"))
        assert r.status == EOLStatus.EOL

    async def test_e10_server_active(self, checker):
        r = await checker.check(_hw("RS700-E10-RS12", category="server"))
        assert r.status == EOLStatus.ACTIVE

    async def test_e11_server_active(self, checker):
        r = await checker.check(_hw("RS720-E11-RS12", category="server"))
        assert r.status == EOLStatus.ACTIVE


class TestASUSFallback:
    async def test_unknown_model(self, checker):
        r = await checker.check(_hw("PRIME X670E-PRO"))
        assert r.status == EOLStatus.UNKNOWN


class TestASUSRegistration:
    def test_auto_registers(self):
        from eol_tool.registry import list_checkers

        checkers = list_checkers()
        assert "asus" in checkers
        assert checkers["asus"] is ASUSChecker
