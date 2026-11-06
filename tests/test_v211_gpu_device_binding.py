import json

import pytest

from tools.v211_gpu_device_binding import (
    GPUDeviceBindingError,
    bind_manifest_data,
    resolve_device_selection,
    write_bound_manifest,
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
        }],
        "vulkan_device_index": 2,
        "vulkan_target_device_match_count": 1,
        "vulkan_loader_available": True,
        "vulkaninfo_succeeded": True,
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
    }
    assert selection["anime4k"] == {
        "backend": "cuda",
        "device_index": 1,
        "device_name": "NVIDIA GeForce GTX 1660 Ti",
    }
    assert selection["binding_configured"] is True
    assert selection["runtime_device_use_verified"] is False


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda value: value["nvidia_smi"].update(devices=[]), "NVIDIA-SMI"),
        (lambda value: value["nvidia_smi"]["devices"].append(
            {"name": "NVIDIA GeForce GTX 1660 Ti"}), "exactly one"),
        (lambda value: value.update(vulkan_device_index=None), "Vulkan"),
        (lambda value: value.update(vulkan_target_device_match_count=2), "Vulkan"),
        (lambda value: value.update(vulkan_loader_available=False), "Vulkan loader"),
        (lambda value: value.update(vram_budget_6gb_detected=False), "Vulkan loader"),
    ],
)
def test_ncnn_selection_fails_closed_on_missing_or_ambiguous_inventory(mutate, message):
    gpu = gpu_report()
    mutate(gpu)
    with pytest.raises(GPUDeviceBindingError, match=message):
        resolve_device_selection(gpu, anime_report())


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
    assert bound["anime4k"]["args"][-3:] == ["--processor", "cuda", "--device", "1"]


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
