import json

import pytest

from tools.v211_gpu_device_binding import (
    GPUDeviceBindingError,
    MIN_FREE_VRAM_MIB,
    bind_manifest_data,
    resolve_device_selection,
    write_bound_manifest,
    validate_free_vram_report,
)
from tools.v211_four_engine_subprocess import ENGINES


def gpu_report():
    return {
        "nvidia_smi": {
            "success": True,
            "devices": [{
                "name": "NVIDIA GeForce GTX 1660 Ti",
                "memory_total_mib": 6144,
                "memory_free_mib": 5600,
            }],
        },
        "vulkan_device_inventory": [{
            "index": 2,
            "name": "NVIDIA GeForce GTX 1660 Ti",
            "vendor_id": 0x10DE,
            "device_id": 0x2184,
            "device_luid_valid": True,
            "device_luid_text": "0x00000001_0x00000002",
            "device_node_mask": 1,
        }],
        "dxgi_adapter_inventory": [{
            "description": "NVIDIA GeForce GTX 1660 Ti",
            "vendor_id": 0x10DE,
            "device_id": 0x2184,
            "luid": [1, 2],
            "luid_text": "0x00000001_0x00000002",
        }],
        "vulkan_inventory_source": "vulkan_loader_native",
        "vulkan_device_index": 2,
        "vulkan_target_device_match_count": 1,
        "vulkan_loader_available": True,
        "vulkaninfo_succeeded": False,
        "vulkan_device_inventory_succeeded": True,
        "vulkan_inventory_source": "vulkan_loader_native",
        "vram_budget_6gb_detected": True,
    }


def anime_report():
    return {
        "status": "ok",
        "processor_probe": {"success": True},
        "device_probe": {"success": True},
        "available_processors": ["cpu", "opencl", "cuda"],
        "device_inventory_by_processor": {
            "cuda": [{"index": 1, "name": "NVIDIA GeForce GTX 1660 Ti"}],
            "opencl": [{"index": 0, "name": "Intel Graphics"}],
        },
        "recommended_gpu_processor_device": {
            "processor": "cuda",
            "device_index": 1,
            "device_name": "NVIDIA GeForce GTX 1660 Ti",
        },
    }


def manifest_data():
    return {
        name: {
            "executable": f"C:/Niyom/{name}.exe",
            "args": ["-i", "{input}", "-o", "{output}", "-f", "png"],
        }
        for name in ENGINES
    }


def test_resolves_separate_vulkan_and_anime4k_device_indexes():
    selection = resolve_device_selection(gpu_report(), anime_report())

    assert selection["ncnn_vulkan"] == {
        "backend": "vulkan",
        "device_index": 2,
        "device_name": "NVIDIA GeForce GTX 1660 Ti",
        "device_luid": "0x00000001_0x00000002",
        "dxgi_adapter_luid": "0x00000001_0x00000002",
        "device_node_mask": 1,
        "luid_match_verified": True,
    }
    assert selection["vulkan_dxgi_luid_binding"]["luid_match_verified"] is True
    assert selection["anime4k"] == {
        "backend": "cuda",
        "device_index": 1,
        "device_name": "NVIDIA GeForce GTX 1660 Ti",
    }
    assert selection["binding_configured"] is True
    assert selection["vram_preflight"] == {
        "total_mib": 6144,
        "free_mib": 5600,
        "minimum_free_mib": MIN_FREE_VRAM_MIB,
        "passed": True,
        "note": "Launch-time snapshot only; not a reservation or peak-memory guarantee.",
    }
    assert selection["runtime_device_use_verified"] is False


@pytest.mark.parametrize("success", [False, None, 1, "false"])
def test_free_vram_report_requires_boolean_success(success):
    gpu = gpu_report()
    gpu["nvidia_smi"]["success"] = success
    with pytest.raises(GPUDeviceBindingError, match="NVIDIA-SMI"):
        validate_free_vram_report(gpu)


def test_free_vram_exactly_at_minimum_is_accepted():
    gpu = gpu_report()
    gpu["nvidia_smi"]["devices"][0]["memory_free_mib"] = MIN_FREE_VRAM_MIB
    selection = resolve_device_selection(gpu, anime_report())
    assert selection["vram_preflight"]["free_mib"] == MIN_FREE_VRAM_MIB


@pytest.mark.parametrize(
    ("free_mib", "message"),
    [
        (MIN_FREE_VRAM_MIB - 1, "insufficient free VRAM"),
        (None, "valid free VRAM"),
        ("5600", "valid free VRAM"),
        (-1, "valid free VRAM"),
        (6145, "exceeds the reported total"),
        (True, "valid free VRAM"),
    ],
)
def test_free_vram_preflight_fails_closed(free_mib, message):
    gpu = gpu_report()
    gpu["nvidia_smi"]["devices"][0]["memory_free_mib"] = free_mib
    with pytest.raises(GPUDeviceBindingError, match=message):
        resolve_device_selection(gpu, anime_report())


def test_free_vram_preflight_rejects_missing_total_capacity():
    gpu = gpu_report()
    gpu["nvidia_smi"]["devices"][0]["memory_total_mib"] = None
    with pytest.raises(GPUDeviceBindingError, match="valid total VRAM"):
        resolve_device_selection(gpu, anime_report())


def test_low_free_vram_does_not_write_runtime_manifest(tmp_path):
    installed = tmp_path / "manifest.json"
    original = manifest_data()
    installed.write_text(json.dumps(original), encoding="utf-8")
    before = installed.read_bytes()
    destination = tmp_path / "work" / "manifest.runtime-bound.json"
    gpu = gpu_report()
    gpu["nvidia_smi"]["devices"][0]["memory_free_mib"] = MIN_FREE_VRAM_MIB - 1

    with pytest.raises(GPUDeviceBindingError, match="insufficient free VRAM"):
        write_bound_manifest(installed, destination, gpu, anime_report())

    assert installed.read_bytes() == before
    assert not destination.exists()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value["nvidia_smi"].update(devices=[]), "NVIDIA-SMI"),
        (lambda value: value["nvidia_smi"].update(success="false"), "NVIDIA-SMI"),
        (lambda value: value["nvidia_smi"].update(success=1), "NVIDIA-SMI"),
        (lambda value: value["nvidia_smi"]["devices"].append(
            {"name": "NVIDIA GeForce GTX 1660 Ti"}), "exactly one"),
        (lambda value: value.update(vulkan_device_index=None), "Vulkan"),
        (lambda value: value.update(vulkan_target_device_match_count=2), "Vulkan"),
        (lambda value: value.update(vulkan_target_device_match_count=True), "Vulkan"),
        (lambda value: value.update(vulkan_loader_available=False), "Vulkan loader"),
        (lambda value: value.update(vulkan_device_inventory_succeeded=False), "Vulkan loader"),
        (lambda value: value.update(vram_budget_6gb_detected=False), "Vulkan loader"),
    ],
)
def test_ncnn_selection_fails_closed_on_missing_or_ambiguous_inventory(mutate, message):
    gpu = gpu_report()
    mutate(gpu)
    with pytest.raises(GPUDeviceBindingError, match=message):
        resolve_device_selection(gpu, anime_report())


@pytest.mark.parametrize(
    ("mutate_gpu", "mutate_anime", "message"),
    [
        (
            lambda gpu: (
                gpu["vulkan_device_inventory"][0].update(index=True),
                gpu.update(vulkan_device_index=True),
            ),
            lambda anime: None,
            "Vulkan",
        ),
        (
            lambda gpu: (
                gpu["vulkan_device_inventory"][0].update(index=1),
                gpu.update(vulkan_device_index=True),
            ),
            lambda anime: None,
            "Vulkan",
        ),
        (
            lambda gpu: None,
            lambda anime: anime["recommended_gpu_processor_device"].update(
                device_index=True
            ),
            "Anime4KCPP recommended device selection",
        ),
    ],
)
def test_resolve_device_selection_rejects_boolean_indexes(
    mutate_gpu, mutate_anime, message
):
    gpu = gpu_report()
    anime = anime_report()
    mutate_gpu(gpu)
    mutate_anime(anime)
    with pytest.raises(GPUDeviceBindingError, match=message):
        resolve_device_selection(gpu, anime)


@pytest.mark.parametrize(
    ("engine_key", "message"),
    [
        ("ncnn_vulkan", "invalid NCNN Vulkan device index"),
        ("anime4k", "invalid Anime4KCPP device index"),
    ],
)
def test_bind_manifest_data_rejects_boolean_indexes(engine_key, message):
    selection = resolve_device_selection(gpu_report(), anime_report())
    selection[engine_key]["device_index"] = True
    with pytest.raises(GPUDeviceBindingError, match=message):
        bind_manifest_data(manifest_data(), selection)


def test_rejects_non_nvidia_vendor_even_if_name_matches():
    gpu = gpu_report()
    gpu["vulkan_device_inventory"][0]["vendor_id"] = 0x8086
    with pytest.raises(GPUDeviceBindingError, match="not an NVIDIA"):
        resolve_device_selection(gpu, anime_report())


def test_anime4k_requires_unique_gpu_device_for_a_gpu_processor():
    anime = anime_report()
    anime["device_inventory_by_processor"]["cuda"].append({
        "index": 2, "name": "NVIDIA GeForce GTX 1660 Ti"
    })
    with pytest.raises(GPUDeviceBindingError, match="ambiguous"):
        resolve_device_selection(gpu_report(), anime)


def test_anime4k_rejects_boolean_inventory_device_index():
    anime = anime_report()
    # bool compares equal to 1 in Python; inventory indexes must still be real ints.
    anime["device_inventory_by_processor"]["cuda"][0]["index"] = True
    with pytest.raises(GPUDeviceBindingError, match="index is missing or ambiguous"):
        resolve_device_selection(gpu_report(), anime)


def test_anime4k_fails_closed_when_only_cpu_is_available():
    anime = anime_report()
    anime["available_processors"] = ["cpu"]
    anime["recommended_gpu_processor_device"] = None
    with pytest.raises(GPUDeviceBindingError, match="no unique"):
        resolve_device_selection(gpu_report(), anime)


def test_binds_ncnn_gpu_and_anime4k_processor_and_device_flags():
    selection = resolve_device_selection(gpu_report(), anime_report())
    bound = bind_manifest_data(manifest_data(), selection)

    for name in ("real_esrgan", "waifu2x", "real_cugan"):
        args = bound[name]["args"]
        assert args[args.index("-g") + 1] == "2"
        assert bound[name]["device_selection"]["backend"] == "vulkan"
        assert bound[name]["device_selection"]["luid_match_verified"] is True
        assert bound[name]["device_selection"]["device_luid"] == "0x00000001_0x00000002"

    anime_args = bound["anime4k"]["args"]
    assert anime_args[anime_args.index("-p") + 1] == "cuda"
    assert anime_args[anime_args.index("-d") + 1] == "1"
    assert bound["anime4k"]["device_selection"]["backend"] == "cuda"


def test_replaces_existing_device_flags_without_duplicates():
    selection = resolve_device_selection(gpu_report(), anime_report())
    manifest = manifest_data()
    manifest["real_esrgan"]["args"] += ["-g", "0"]
    manifest["anime4k"]["args"] += ["--processor", "auto", "--device", "0"]

    bound = bind_manifest_data(manifest, selection)

    assert bound["real_esrgan"]["args"].count("-g") == 1
    assert bound["real_esrgan"]["args"][-1] == "2"
    assert bound["anime4k"]["args"].count("--processor") == 1
    assert bound["anime4k"]["args"][-4:] == ["--processor", "cuda", "--device", "1"]


def test_duplicate_gpu_flags_are_rejected():
    selection = resolve_device_selection(gpu_report(), anime_report())
    manifest = manifest_data()
    manifest["waifu2x"]["args"] += ["-g", "0", "--gpu", "1"]

    with pytest.raises(GPUDeviceBindingError, match="duplicate CLI option"):
        bind_manifest_data(manifest, selection)


def test_write_bound_manifest_is_ephemeral_and_does_not_change_installed_file(tmp_path):
    installed = tmp_path / "manifest.json"
    original = manifest_data()
    installed.write_text(json.dumps(original), encoding="utf-8")
    before = installed.read_bytes()
    destination = tmp_path / "work" / "manifest.runtime-bound.json"

    selection = write_bound_manifest(
        installed, destination, gpu_report(), anime_report()
    )

    assert installed.read_bytes() == before
    bound = json.loads(destination.read_text(encoding="utf-8"))
    assert bound["real_cugan"]["args"][-2:] == ["-g", "2"]
    assert bound["anime4k"]["args"][-4:] == ["-p", "cuda", "-d", "1"]
    assert selection["runtime_device_use_verified"] is False
    with pytest.raises(GPUDeviceBindingError, match="already exists"):
        write_bound_manifest(installed, destination, gpu_report(), anime_report())



@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda gpu: gpu["vulkan_device_inventory"][0].update(
                device_luid_valid=False, device_luid_text=None
            ),
            "deviceLUID is not valid",
        ),
        (
            lambda gpu: gpu["dxgi_adapter_inventory"][0].update(
                luid_text="0x00000003_0x00000004"
            ),
            "does not match",
        ),
        (
            lambda gpu: gpu.update(dxgi_adapter_inventory=[]),
            "DXGI must expose exactly one",
        ),
        (
            lambda gpu: gpu["vulkan_device_inventory"][0].update(device_node_mask=3),
            "deviceNodeMask is invalid",
        ),
        (
            lambda gpu: gpu.update(vulkan_inventory_source="vulkaninfo"),
            "native Vulkan loader inventory",
        ),
    ],
)
def test_vulkan_to_dxgi_luid_binding_fails_closed(mutate, message):
    gpu = gpu_report()
    mutate(gpu)
    with pytest.raises(GPUDeviceBindingError, match=message):
        resolve_device_selection(gpu, anime_report())


def test_duplicate_dxgi_target_adapter_is_ambiguous():
    gpu = gpu_report()
    duplicate = dict(gpu["dxgi_adapter_inventory"][0])
    duplicate["luid_text"] = "0x00000005_0x00000006"
    duplicate["luid"] = [5, 6]
    gpu["dxgi_adapter_inventory"].append(duplicate)
    with pytest.raises(GPUDeviceBindingError, match="exactly one unambiguous"):
        resolve_device_selection(gpu, anime_report())


def test_bind_manifest_data_requires_verified_vulkan_dxgi_luid():
    selection = resolve_device_selection(gpu_report(), anime_report())
    selection["ncnn_vulkan"]["luid_match_verified"] = False
    with pytest.raises(GPUDeviceBindingError, match="LUID binding is not verified"):
        bind_manifest_data(manifest_data(), selection)
