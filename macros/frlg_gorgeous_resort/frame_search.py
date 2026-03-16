"""フレーム検索・連続区間検出ロジック

指定した初期 Seed ＋ フレーム範囲に対して
アキホおねだりのポケモン・アイテム結果を全列挙する。
仕様: spec/macro/frlg_gorgeous_resort/selphy_rewards.md §7
"""

from __future__ import annotations

from dataclasses import dataclass

from frlg_initial_seed.lcg32 import LCG32

from .selphy_logic import (
    ITEM_TABLE,
    LUXURY_BALL,
    MAX_RETRY,
)
from .species_data import INTERNAL_TO_NAME, NUM_SPECIES_CODES


@dataclass(frozen=True)
class AkihoResult:
    """1フレーム分のアキホおねだり結果"""

    frame: int
    species_code: int
    species_name: str
    item: str
    rng_pokemon_consumed: int


def search_akiho_frames(
    initial_seed: int,
    pokedex: set[int],
    frame_min: int,
    frame_max: int,
) -> list[AkihoResult]:
    """指定フレーム範囲でアキホおねだりの結果を全列挙する。

    Args:
        initial_seed: 16bit 初期Seed（0x0000〜0xFFFF）
        pokedex: 図鑑登録済みポケモンの内部コード集合
        frame_min: 検索開始フレーム
        frame_max: 検索終了フレーム

    Returns:
        各フレームの結果リスト
    """
    results: list[AkihoResult] = []

    for frame in range(frame_min, frame_max + 1):
        lcg = LCG32(initial_seed)
        lcg.advance(frame)

        # ポケモン決定
        pokemon_consumed = 0
        species_code = 0

        for _ in range(MAX_RETRY):
            rand_value = lcg.get_rand()
            pokemon_consumed += 1
            code = (rand_value % NUM_SPECIES_CODES) + 1
            if code in pokedex:
                species_code = code
                break
        else:
            # フォールバック: 逆順検索
            for code in range(NUM_SPECIES_CODES, 0, -1):
                if code in pokedex:
                    species_code = code
                    break

        # アイテム決定
        rand_value = lcg.get_rand()
        value = rand_value % 100
        if value >= 30:
            item = LUXURY_BALL
        else:
            item = ITEM_TABLE[value // 5]

        results.append(
            AkihoResult(
                frame=frame,
                species_code=species_code,
                species_name=INTERNAL_TO_NAME.get(species_code, "???"),
                item=item,
                rng_pokemon_consumed=pokemon_consumed,
            )
        )

    return results


def find_consecutive_runs(
    results: list[AkihoResult],
    min_run_length: int = 5,
) -> list[list[AkihoResult]]:
    """同一ポケモン+アイテムが min_run_length 以上連続する区間を返す。"""
    runs: list[list[AkihoResult]] = []
    current_run: list[AkihoResult] = []

    for result in results:
        if (
            current_run
            and current_run[-1].species_code == result.species_code
            and current_run[-1].item == result.item
        ):
            current_run.append(result)
        else:
            if len(current_run) >= min_run_length:
                runs.append(current_run)
            current_run = [result]

    if len(current_run) >= min_run_length:
        runs.append(current_run)

    return runs
