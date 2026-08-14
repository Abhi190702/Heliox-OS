from pilot.system.sysinfo import _format_system_health_review


def test_health_review_prioritizes_measured_pressure_and_stays_read_only():
    output = _format_system_health_review(
        {
            "cpu_percent": 26.0,
            "memory_percent": 91.0,
            "memory_available_gb": 2.8,
            "disks": [{"device": "C:", "mountpoint": "C:\\", "percent": 88.0, "free_gb": 14.0}],
            "battery_percent": 73.0,
            "battery_plugged": True,
            "process_count": 42,
            "top_processes": [{"pid": 123, "name": "example.exe", "memory_mb": 900.0}],
        }
    )

    assert "Memory is 91.0% used" in output
    assert "C: at 88.0% used" in output
    assert "example.exe (PID 123, 900 MB)" in output
    assert "No processes or files were changed." in output
    assert output.index("Memory is 91.0% used") < output.index("C: at 88.0% used")
