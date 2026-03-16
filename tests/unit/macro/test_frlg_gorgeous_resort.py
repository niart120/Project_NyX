"""FRLG ゴージャスリゾート アキホおねだりマクロ — ユニットテスト

species_data / selphy_logic / frame_search / recognizer / config のテストを提供する。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_macros_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "macros")
if _macros_dir not in sys.path:
    sys.path.insert(0, _macros_dir)

from frlg_initial_seed.lcg32 import LCG32
from frlg_gorgeous_resort.config import FrlgGorgeousResortConfig
from frlg_gorgeous_resort.frame_search import (
    AkihoResult,
    find_consecutive_runs,
    search_akiho_frames,
)
from frlg_gorgeous_resort.recognizer import (
    _edit_distance,
    match_item,
    matches_any_target,
)
from frlg_gorgeous_resort.selphy_logic import (
    ITEM_TABLE,
    LUXURY_BALL,
    MAX_RETRY,
    determine_item,
    determine_pokemon,
)
from frlg_gorgeous_resort.species_data import (
    DUMMY_CODE_END,
    DUMMY_CODE_START,
    INTERNAL_TO_NAME,
    INTERNAL_TO_NATIONAL,
    NAME_TO_NATIONAL,
    NATIONAL_TO_INTERNAL,
    NATIONAL_TO_NAME,
    NUM_SPECIES_CODES,
    is_dummy,
)


# ============================================================
# species_data テスト
# ============================================================


class TestSpeciesData:
    """species_data モジュールのテスト"""

    def test_internal_to_national_length(self):
        """INTERNAL_TO_NATIONAL テーブルの長さが 412 (0〜411 + 欠番0)"""
        assert len(INTERNAL_TO_NATIONAL) == 412

    def test_kanto_johto_identity(self):
        """内部コード 1〜251 は全国図鑑番号と一致"""
        for i in range(1, 252):
            assert INTERNAL_TO_NATIONAL[i] == i

    def test_dummy_range(self):
        """ダミー範囲 (252〜276) のコードは図鑑番号 387〜411"""
        for i in range(DUMMY_CODE_START, DUMMY_CODE_END + 1):
            nat = INTERNAL_TO_NATIONAL[i]
            assert 387 <= nat <= 411

    def test_hoenn_first_entry(self):
        """ホウエン先頭: 内部コード 277 = 全国図鑑 252 (キモリ)"""
        assert INTERNAL_TO_NATIONAL[277] == 252

    def test_hoenn_last_entry(self):
        """ホウエン末尾: 内部コード 411 = 全国図鑑 358 (チリーン)"""
        assert INTERNAL_TO_NATIONAL[411] == 358

    def test_is_dummy(self):
        """is_dummy() がダミー範囲を正しく判定する"""
        assert is_dummy(252)
        assert is_dummy(276)
        assert not is_dummy(251)
        assert not is_dummy(277)
        assert not is_dummy(1)

    def test_national_to_internal_roundtrip(self):
        """NATIONAL_TO_INTERNAL の逆引きが正しい (カントー 1〜251)"""
        for nat in range(1, 252):
            assert NATIONAL_TO_INTERNAL[nat] == nat

    def test_name_to_national_pikachu(self):
        """ピカチュウの名前→全国図鑑番号が25"""
        assert NAME_TO_NATIONAL["ピカチュウ"] == 25

    def test_national_to_name_all_386(self):
        """NATIONAL_TO_NAME に 386 種すべてが含まれている"""
        assert len(NATIONAL_TO_NAME) == 386

    def test_internal_to_name_excludes_dummies(self):
        """INTERNAL_TO_NAME にダミーコードが含まれていない"""
        for code in range(DUMMY_CODE_START, DUMMY_CODE_END + 1):
            assert code not in INTERNAL_TO_NAME


# ============================================================
# selphy_logic テスト
# ============================================================


class TestDetermineItem:
    """determine_item() のテスト"""

    def test_luxury_ball_high_rand(self):
        """rand % 100 >= 30 のときゴージャスボール"""
        # 0x0000 から3回 advance した seed を使い、
        # get_rand() が 30 以上になるよう seed を調整
        lcg = LCG32(0)
        # advance until we get rand % 100 >= 30
        for _ in range(100):
            test_lcg = LCG32(lcg.seed)
            r = test_lcg.get_rand()
            if r % 100 >= 30:
                result = determine_item(lcg)
                assert result == LUXURY_BALL
                return
            lcg.advance()
        pytest.fail("テスト用の乱数値が見つからない")

    def test_items_low_rand(self):
        """rand % 100 < 30 のとき ITEM_TABLE から選択される"""
        # 特定の seed から各アイテムが返ることを確認
        lcg = LCG32(0)
        found_items: set[str] = set()
        for _ in range(1000):
            test_lcg = LCG32(lcg.seed)
            r_peek = LCG32(lcg.seed)
            r_peek.advance()
            val = ((r_peek.seed >> 16) & 0xFFFF) % 100
            if val < 30:
                item = determine_item(test_lcg)
                assert item in ITEM_TABLE
                found_items.add(item)
            lcg.advance()
        # 1000 回もあれば全 6 アイテムが出るはず
        assert len(found_items) == 6


class TestDeterminePokemon:
    """determine_pokemon() のテスト"""

    def test_registered_pokemon_found(self):
        """登録済みポケモンが正しく選ばれる"""
        # 全ポケモン登録済みの場合
        full_pokedex: set[int] = set(range(1, 412)) - set(
            range(DUMMY_CODE_START, DUMMY_CODE_END + 1)
        )
        lcg = LCG32(0x1234)
        lcg.advance(100)
        result = determine_pokemon(lcg, full_pokedex)
        assert result in full_pokedex

    def test_fallback_when_no_match_in_random(self):
        """Phase 1 で見つからない場合、Phase 2 で逆順検索する"""
        # 内部コード 411 のみ登録
        pokedex: set[int] = {411}
        lcg = LCG32(0)
        lcg.advance(50)

        result = determine_pokemon(lcg, pokedex)
        assert result == 411

    def test_empty_pokedex_raises(self):
        """空の図鑑で RuntimeError が発生する"""
        lcg = LCG32(0)
        with pytest.raises(RuntimeError):
            determine_pokemon(lcg, set())

    def test_consumes_rng(self):
        """ポケモン決定で少なくとも 1 回は乱数が消費される"""
        full_pokedex: set[int] = set(range(1, 252))
        lcg = LCG32(0x5678)
        seed_before = lcg.seed
        determine_pokemon(lcg, full_pokedex)
        assert lcg.seed != seed_before


# ============================================================
# frame_search テスト
# ============================================================


class TestFrameSearch:
    """search_akiho_frames() / find_consecutive_runs() のテスト"""

    @pytest.fixture()
    def full_pokedex(self) -> set[int]:
        return set(range(1, 412)) - set(
            range(DUMMY_CODE_START, DUMMY_CODE_END + 1)
        )

    def test_returns_correct_frame_count(self, full_pokedex: set[int]):
        """指定フレーム範囲内の結果数が正しい"""
        results = search_akiho_frames(
            initial_seed=0x1234,
            pokedex=full_pokedex,
            frame_min=100,
            frame_max=109,
        )
        assert len(results) == 10

    def test_result_fields(self, full_pokedex: set[int]):
        """AkihoResult にすべてのフィールドが含まれる"""
        results = search_akiho_frames(
            initial_seed=0x0000,
            pokedex=full_pokedex,
            frame_min=50,
            frame_max=50,
        )
        r = results[0]
        assert r.frame == 50
        assert 1 <= r.species_code <= NUM_SPECIES_CODES
        assert isinstance(r.species_name, str)
        assert isinstance(r.item, str)
        assert r.rng_pokemon_consumed >= 1

    def test_find_consecutive_runs_basic(self):
        """同一ポケモン+アイテムの連続区間が正しく検出される"""
        run_results = [
            AkihoResult(
                frame=i,
                species_code=25,
                species_name="ピカチュウ",
                item=LUXURY_BALL,
                rng_pokemon_consumed=1,
            )
            for i in range(10)
        ]
        runs = find_consecutive_runs(run_results, min_run_length=5)
        assert len(runs) == 1
        assert len(runs[0]) == 10

    def test_find_consecutive_runs_no_match(self):
        """連続数が閾値未満の場合、空リストを返す"""
        results = [
            AkihoResult(
                frame=i,
                species_code=i % 3 + 1,
                species_name="test",
                item=LUXURY_BALL,
                rng_pokemon_consumed=1,
            )
            for i in range(10)
        ]
        runs = find_consecutive_runs(results, min_run_length=5)
        assert runs == []


# ============================================================
# recognizer テスト
# ============================================================


class TestEditDistance:
    """_edit_distance() のテスト"""

    def test_identical(self):
        assert _edit_distance("ピカチュウ", "ピカチュウ") == 0

    def test_one_char_diff(self):
        assert _edit_distance("ピカチュウ", "ピカチュオ") == 1

    def test_empty_strings(self):
        assert _edit_distance("", "") == 0

    def test_one_empty(self):
        assert _edit_distance("abc", "") == 3


class TestMatchesAnyTarget:
    """matches_any_target() のテスト"""

    def test_exact_match(self):
        assert matches_any_target("ピカチュウ", ["ピカチュウ", "リザードン"])

    def test_fuzzy_match(self):
        # 1文字違い → 編集距離1 で一致扱い
        assert matches_any_target("ピカチュオ", ["ピカチュウ"])

    def test_no_match(self):
        assert not matches_any_target("フシギダネ", ["ピカチュウ", "リザードン"])


class TestMatchItem:
    """match_item() のテスト"""

    def test_luxury_ball(self):
        assert match_item("ゴージャスボールを もらった!") == "ゴージャスボール"

    def test_big_pearl(self):
        assert match_item("おおきなしんじゅを もらった!") == "おおきなしんじゅ"

    def test_pearl_not_confused_with_big_pearl(self):
        # "しんじゅ" は "おおきなしんじゅ" より短いので、先に長い方が照合される
        assert match_item("しんじゅを もらった!") == "しんじゅ"

    def test_bag_full(self):
        assert match_item("おかばんが いっぱいです!") == "BAG_FULL"

    def test_unknown(self):
        assert match_item("不明なテキスト") is None


# ============================================================
# config テスト
# ============================================================


class TestConfig:
    """FrlgGorgeousResortConfig のテスト"""

    def test_defaults(self):
        cfg = FrlgGorgeousResortConfig()
        assert cfg.language == "JPN"
        assert cfg.frame1 == 2347
        assert cfg.frame2 == 610
        assert cfg.target_item == "ゴージャスボール"
        assert cfg.target_count == 9999
        assert cfg.target_pokemon == []
        assert cfg.pokedex == []
        assert cfg.fps == 60.0
        assert cfg.frame1_offset == 0
        assert cfg.frame2_offset == 322

    def test_from_args(self):
        args = {
            "frame1": 3000,
            "frame2": 700,
            "target_item": "ふしぎなアメ",
            "target_count": 50,
            "target_pokemon": ["ピカチュウ", "リザードン"],
            "pokedex": [1, 4, 7, 25],
            "frame2_offset": 300,
        }
        cfg = FrlgGorgeousResortConfig.from_args(args)
        assert cfg.frame1 == 3000
        assert cfg.frame2 == 700
        assert cfg.target_item == "ふしぎなアメ"
        assert cfg.target_count == 50
        assert cfg.target_pokemon == ["ピカチュウ", "リザードン"]
        assert cfg.pokedex == [1, 4, 7, 25]
        assert cfg.frame2_offset == 300
