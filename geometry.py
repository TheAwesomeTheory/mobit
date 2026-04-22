"""Shared geometry utilities for DadoVida assembly scripts."""

import json
import math

import numpy as np


def rot_x(d: float) -> np.ndarray:
    r = math.radians(d); c = math.cos(r); s = math.sin(r)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_y(d: float) -> np.ndarray:
    r = math.radians(d); c = math.cos(r); s = math.sin(r)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_z(d: float) -> np.ndarray:
    r = math.radians(d); c = math.cos(r); s = math.sin(r)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def load_pins(path: str) -> dict:
    with open(path) as f:
        return json.load(f)["pins"]


def load_connections(path: str) -> list:
    with open(path) as f:
        return json.load(f)["connections"]


def pin_to_assembly(pin: dict, rotation: np.ndarray, translation: np.ndarray) -> np.ndarray:
    local = np.array([pin["x"], pin["y"], pin["z"]])
    return rotation @ local + translation


class BoardInScene:
    """A board positioned in the assembly, with pin access by side.

    Wraps a board's pin data, rotation, translation, and bounding box
    so you can query pin positions on either face of the board.

    Args:
        name: board identifier (e.g., "xiao", "bno085")
        pins: dict of pin_name → {"x", "y", "z", ...} in board-local coords
        rotation: 3x3 rotation matrix (local → assembly)
        translation: 3-vector translation (local → assembly)
        chip_side_z: Z value in assembly space of the chip/component face
        non_chip_side_z: Z value in assembly space of the opposite face
    """

    def __init__(self, name, pins, rotation, translation, chip_side_z, non_chip_side_z):
        self.name = name
        self.pins = pins
        self.rotation = rotation
        self.translation = translation
        self.chip_side_z = chip_side_z
        self.non_chip_side_z = non_chip_side_z

    def get_pin(self, pin_name, chip_side=True):
        """Get a pin's 3D position in assembly space.

        Args:
            pin_name: name of the pin (must exist in self.pins)
            chip_side: if True, return position on the chip/component face;
                       if False, return position on the opposite face.

        Returns:
            np.ndarray of [x, y, z] in assembly space.
            XY comes from the pin's local coords transformed to assembly space.
            Z is forced to the requested face of the board.
        """
        pin = self.pins[pin_name]
        pos = pin_to_assembly(pin, self.rotation, self.translation)
        pos[2] = self.chip_side_z if chip_side else self.non_chip_side_z
        return pos

    def all_pins(self, chip_side=True):
        """Get all pin positions on the requested face.

        Returns dict of pin_name → np.ndarray.
        """
        return {name: self.get_pin(name, chip_side) for name in self.pins}
