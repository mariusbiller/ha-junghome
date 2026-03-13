from __future__ import annotations


def iter_datapoints_by_type(device: dict, datapoint_type: str):
    """Yield datapoints matching a specific type."""
    for datapoint in device.get("datapoints", []):
        if datapoint.get("type") == datapoint_type:
            yield datapoint


def find_datapoint(device: dict, datapoint_type: str) -> dict | None:
    """Return first datapoint of a given type."""
    for datapoint in iter_datapoints_by_type(device, datapoint_type):
        return datapoint
    return None


def get_datapoint_id(device: dict, datapoint_type: str) -> str | None:
    """Return first datapoint ID for a given type."""
    datapoint = find_datapoint(device, datapoint_type)
    if datapoint is None:
        return None
    return datapoint.get("id")


def extract_quantity_label_unit(values: list) -> tuple[str | None, str | None]:
    """Extract quantity label and unit from quantity datapoint values."""
    quantity_label = None
    quantity_unit = None

    for value_item in values:
        key = value_item.get("key")
        value = value_item.get("value")
        if not isinstance(value, str):
            continue
        if key == "quantity_label":
            quantity_label = value.strip()
        elif key == "quantity_unit":
            quantity_unit = value.strip()

    return quantity_label, quantity_unit
