"""
Módulo de grade de mapa estilo batalha naval para Kanto.
Coordenadas: linha = letra (A–E), coluna = número (1–6).
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
import json
from pathlib import Path


@dataclass
class GridCell:
    coord: str          # ex: "B3"
    location_id: Optional[str]
    name: Optional[str]
    kind: str           # city, route, cave, forest, ocean
    icon: str           # símbolo de 2 chars para exibição

    @property
    def row(self) -> str:
        return self.coord[0]

    @property
    def col(self) -> int:
        return int(self.coord[1:])

    @property
    def passable(self) -> bool:
        return self.kind != "ocean" and self.location_id is not None

    @classmethod
    def from_dict(cls, data: dict) -> "GridCell":
        return cls(
            coord=data["coord"],
            location_id=data.get("location_id"),
            name=data.get("name"),
            kind=data.get("kind", "route"),
            icon=data.get("icon", "~~"),
        )


@dataclass
class KantoGrid:
    rows: list[str]
    cols: list[int]
    cells: dict[str, GridCell] = field(default_factory=dict)   # coord → cell

    @classmethod
    def from_dict(cls, data: dict) -> "KantoGrid":
        rows = data["rows"]
        cols = data["cols"]
        cells = {item["coord"]: GridCell.from_dict(item) for item in data["cells"]}
        return cls(rows=rows, cols=cols, cells=cells)

    def get(self, coord: str) -> Optional[GridCell]:
        return self.cells.get(coord)

    def cell_for_location(self, location_name_or_id: str) -> Optional[GridCell]:
        """Devolve a célula que contém um local pelo nome ou ID."""
        for cell in self.cells.values():
            if cell.location_id == location_name_or_id or cell.name == location_name_or_id:
                return cell
        return None

    def adjacent(self, coord: str) -> list[GridCell]:
        """Retorna células passáveis adjacentes (N/S/L/O)."""
        cell = self.cells.get(coord)
        if not cell:
            return []
        row_idx = self.rows.index(cell.row)
        col_idx = self.cols.index(cell.col)
        neighbors = []
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = row_idx + dr, col_idx + dc
            if 0 <= nr < len(self.rows) and 0 <= nc < len(self.cols):
                neighbor_coord = f"{self.rows[nr]}{self.cols[nc]}"
                neighbor = self.cells.get(neighbor_coord)
                if neighbor and neighbor.passable:
                    neighbors.append(neighbor)
        return neighbors


def load_grid(data_dir: Path) -> KantoGrid:
    path = data_dir / "map_grid.json"
    return KantoGrid.from_dict(json.loads(path.read_text(encoding="utf-8")))
