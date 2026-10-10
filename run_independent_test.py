"""Isolated NiyomSilp Independent Core desktop test EXE entrypoint."""
import os

if __name__ == "__main__":
    if os.environ.get("NIYOMSIL_INDEPENDENT_SMOKE") == "1":
        from independent_core.desktop_adapter import DesktopTestAdapter
        from independent_core.print_output import PrintSpec
        from independent_core.icc_library import list_external_profiles
        adapter = DesktopTestAdapter()
        assert adapter.available, "No bundled x4plus model"
        assert PrintSpec(width=100, height=50, dpi=150).target_pixels()[0] > 0
        print("NiyomSilp Independent Core TEST import and model paths OK")
        raise SystemExit(0)
    from independent_core.gui_test import main
    main()
