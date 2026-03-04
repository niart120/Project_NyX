"""
FRLG 初期Seed特定マクロ — ユニットテスト

LCG32 / nature / pokemon_gen / seed_solver のテストを提供する。
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# macros/ ディレクトリをインポートパスに追加
_macros_dir = str(Path(__file__).resolve().parent.parent.parent.parent / "macros")
if _macros_dir not in sys.path:
    sys.path.insert(0, _macros_dir)


# ============================================================
# LCG32 テスト
# ============================================================

from frlg_initial_seed.lcg32 import LCG32


class TestLCG32:
    """LCG32 乱数生成器のテスト"""

    def test_initial_seed(self):
        """初期化時に seed が正しく設定される"""
        lcg = LCG32(0x1234)
        assert lcg.seed == 0x1234

    def test_mask_on_init(self):
        """初期化時に 32bit マスクが適用される"""
        lcg = LCG32(0x1_0000_0000)
        assert lcg.seed == 0

    def test_advance_once(self):
        """1 step 前進の計算が正しい"""
        lcg = LCG32(0)
        lcg.advance()
        # seed = (0x41C64E6D * 0 + 0x6073) & 0xFFFFFFFF = 0x6073
        assert lcg.seed == 0x00006073

    def test_advance_sequence(self):
        """複数回前進した結果が既知の値と一致する"""
        lcg = LCG32(0)
        seeds = []
        for _ in range(5):
            lcg.advance()
            seeds.append(lcg.seed)
        # 手動計算:
        # s0 = 0
        # s1 = 0x00006073
        # s2 = (0x41C64E6D * 0x6073 + 0x6073) & mask
        assert seeds[0] == 0x00006073
        # 2回目以降は既知の LCG シーケンスで検証
        expected_s2 = (0x41C64E6D * 0x00006073 + 0x00006073) & 0xFFFFFFFF
        assert seeds[1] == expected_s2

    def test_back_reverses_advance(self):
        """back() が advance() の逆操作として機能する"""
        lcg = LCG32(0xABCD)
        original = lcg.seed
        lcg.advance(5)
        lcg.back(5)
        assert lcg.seed == original

    def test_get_rand(self):
        """get_rand() が advance(1) + 上位 16bit を返す"""
        lcg = LCG32(0)
        rand = lcg.get_rand()
        # advance 後の seed: 0x00006073 → 上位16bit: 0
        assert rand == 0
        # 2回目
        rand2 = lcg.get_rand()
        expected_seed = (0x41C64E6D * 0x00006073 + 0x00006073) & 0xFFFFFFFF
        assert rand2 == (expected_seed >> 16) & 0xFFFF

    def test_advance_n(self):
        """advance(n) は advance() × n回と同等"""
        lcg1 = LCG32(42)
        lcg1.advance(10)

        lcg2 = LCG32(42)
        for _ in range(10):
            lcg2.advance()

        assert lcg1.seed == lcg2.seed

    def test_back_n(self):
        """back(n) は back() × n回と同等"""
        lcg1 = LCG32(42)
        lcg1.advance(10)
        lcg1.back(10)

        assert lcg1.seed == 42


# ============================================================
# nature テスト
# ============================================================

from frlg_initial_seed.nature import (
    NATURE_JPN_TO_EN,
    NATURE_NAMES,
    NATURE_TO_ID,
    get_nature_multipliers,
)


class TestNature:
    """性格テーブルのテスト"""

    def test_nature_count(self):
        """25 種類の性格が定義されている"""
        assert len(NATURE_NAMES) == 25
        assert len(NATURE_TO_ID) == 25

    def test_nature_id_round_trip(self):
        """名前 → ID → 名前の往復変換"""
        for name in NATURE_NAMES:
            idx = NATURE_TO_ID[name]
            assert NATURE_NAMES[idx] == name

    def test_jpn_to_en_complete(self):
        """日本語名 → 英語名テーブルが全25種をカバー"""
        assert len(NATURE_JPN_TO_EN) == 25
        en_names = set(NATURE_JPN_TO_EN.values())
        assert en_names == set(NATURE_NAMES)

    def test_adamant_multipliers(self):
        """Adamant: Attack ×1.1, SpecialAttack ×0.9"""
        mult = get_nature_multipliers("Adamant")
        assert mult["Attack"] == pytest.approx(1.1)
        assert mult["SpecialAttack"] == pytest.approx(0.9)
        assert mult["Defense"] == pytest.approx(1.0)
        assert mult["Speed"] == pytest.approx(1.0)
        assert mult["SpecialDefense"] == pytest.approx(1.0)

    def test_hardy_neutral(self):
        """Hardy（無補正）: 全ステータス ×1.0"""
        mult = get_nature_multipliers("Hardy")
        for key in ("Attack", "Defense", "Speed", "SpecialAttack", "SpecialDefense"):
            assert mult[key] == pytest.approx(1.0)

    def test_timid_multipliers(self):
        """Timid: Speed ×1.1, Attack ×0.9"""
        mult = get_nature_multipliers("Timid")
        assert mult["Speed"] == pytest.approx(1.1)
        assert mult["Attack"] == pytest.approx(0.9)


# ============================================================
# pokemon_gen テスト
# ============================================================

from frlg_initial_seed.pokemon_gen import Pokemon, generate_pokemon


class TestPokemonGen:
    """個体生成ロジックのテスト"""

    def test_generate_pokemon_consumes_4_steps(self):
        """generate_pokemon は LCG を 4step 消費する"""
        lcg = LCG32(0x1234)
        lcg_copy = LCG32(0x1234)
        lcg_copy.advance(4)

        generate_pokemon(lcg)
        assert lcg.seed == lcg_copy.seed

    def test_pid_composition(self):
        """PID = lid | (hid << 16)"""
        lcg = LCG32(0x1234)
        lcg_copy = LCG32(0x1234)

        lid = lcg_copy.get_rand()
        hid = lcg_copy.get_rand()
        expected_pid = lid | (hid << 16)

        pokemon = generate_pokemon(lcg)
        assert pokemon.pid == expected_pid

    def test_nature_id(self):
        """nature_id = PID % 25"""
        lcg = LCG32(0x5678)
        pokemon = generate_pokemon(lcg)
        assert pokemon.nature_id == pokemon.pid % 25

    def test_ivs_in_range(self):
        """IV は 0〜31 の範囲"""
        for seed in (0, 0x1234, 0xABCD, 0xFFFF):
            lcg = LCG32(seed)
            p = generate_pokemon(lcg)
            for iv in (p.iv_hp, p.iv_atk, p.iv_def, p.iv_spa, p.iv_spd, p.iv_spe):
                assert 0 <= iv <= 31

    def test_calc_stats_lugia_example(self):
        """仕様書 §7 の計算例: ルギア Lv.70 Adamant

        HP=238, Atk=149, Def=189, SpA=130, SpD=229, Spe=162
        """
        # IV: HP=15, Atk=8, Def=3, SpA=20, SpD=12, Spe=5
        pokemon = Pokemon(
            pid=0,  # PID は calc_stats には影響しない
            nature_id=3,  # Adamant
            iv_hp=15,
            iv_atk=8,
            iv_def=3,
            iv_spa=20,
            iv_spd=12,
            iv_spe=5,
        )

        base_stats = (106, 90, 130, 90, 154, 110)
        level = 70
        nature_mult = get_nature_multipliers("Adamant")

        stats = pokemon.calc_stats(base_stats, level, nature_mult)
        assert stats == (238, 149, 189, 130, 229, 162)


# ============================================================
# seed_solver テスト
# ============================================================

from frlg_initial_seed.seed_solver import solve_initial_seed


class TestSeedSolver:
    """Seed 逆算ロジックのテスト"""

    # ルギア Lv.70 の種族値
    BASE_STATS = (106, 90, 130, 90, 154, 110)
    LEVEL = 70

    def test_known_seed_returns_hex(self):
        """既知の条件から正しい Seed が返ること。

        Seed=0x0000, advance=741 で生成される個体を事前計算し、
        それを入力として solve_initial_seed に渡す。
        """
        # Seed 0x0000, advance 741 で個体を生成
        lcg = LCG32(0x0000)
        lcg.advance(741)
        pokemon = generate_pokemon(lcg)

        nature = NATURE_NAMES[pokemon.nature_id]
        nature_mult = get_nature_multipliers(nature)
        observed_stats = pokemon.calc_stats(self.BASE_STATS, self.LEVEL, nature_mult)

        seed, advance = solve_initial_seed(
            observed_stats=observed_stats,
            base_stats=self.BASE_STATS,
            level=self.LEVEL,
            min_advance=741,
            max_advance=741,
        )

        # 結果は "0000" または一意な Seed
        assert seed != "False"
        assert seed != "MULT"
        # advance が返ること
        assert advance == 741

    def test_false_on_impossible_stats(self):
        """不可能な実数値で ("False", None) が返る"""
        seed, advance = solve_initial_seed(
            observed_stats=(999, 999, 999, 999, 999, 999),
            base_stats=self.BASE_STATS,
            level=self.LEVEL,
            min_advance=741,
            max_advance=749,
        )
        assert seed == "False"
        assert advance is None

    def test_narrow_range_specific_seed(self):
        """特定 Seed + 狭い advance 範囲で一意に特定できること"""
        # 複数の seed で試行し、一意に特定できるケースを見つける
        for test_seed in range(0, 100):
            lcg = LCG32(test_seed)
            lcg.advance(745)
            pokemon = generate_pokemon(lcg)

            nature = NATURE_NAMES[pokemon.nature_id]
            nature_mult = get_nature_multipliers(nature)
            stats = pokemon.calc_stats(self.BASE_STATS, self.LEVEL, nature_mult)

            seed, advance = solve_initial_seed(
                observed_stats=stats,
                base_stats=self.BASE_STATS,
                level=self.LEVEL,
                min_advance=745,
                max_advance=745,
            )

            # 結果は False でないべき（少なくとも test_seed が見つかるはず）
            assert seed != "False", f"Seed {test_seed:04X} が見つからなかった"

            if seed != "MULT":
                # 一意に特定されたなら、test_seed のはず
                assert seed == f"{test_seed:04X}"
                assert advance == 745
                return  # テスト成功

        pytest.fail("100件の seed で一意に特定できるケースが見つからなかった")

    def test_stats_only_seed_resolution(self):
        """実数値のみで Seed 逆算ができること"""
        # Seed 0x0000, advance 741 で個体を生成
        lcg = LCG32(0x0000)
        lcg.advance(741)
        pokemon = generate_pokemon(lcg)

        nature = NATURE_NAMES[pokemon.nature_id]
        nature_mult = get_nature_multipliers(nature)
        observed_stats = pokemon.calc_stats(self.BASE_STATS, self.LEVEL, nature_mult)

        seed, advance = solve_initial_seed(
            observed_stats=observed_stats,
            base_stats=self.BASE_STATS,
            level=self.LEVEL,
            min_advance=741,
            max_advance=741,
        )

        # 候補が見つかる（False でない）
        assert seed != "False"
        # 一意特定 or MULT のどちらかになりうる
        if seed != "MULT":
            assert seed == "0000"
            assert advance == 741

    # --------------------------------------------------------
    # 実機データによる回帰テスト
    # --------------------------------------------------------

    def test_real_data_jolly_unique(self):
        """実機データ: ようき (Jolly) — 一意に Seed 特定できるケース

        実機観測値:
            Stats: HP=231, Atk=149, Def=204, SpA=119, SpD=240, Spe=182
            IV: H=5, A=27, B=25, C=3, D=28, S=10
            初期Seed=0x557B, advance=1708, LCG state=0x35D25317
        """
        seed, advance = solve_initial_seed(
            observed_stats=(231, 149, 204, 119, 240, 182),
            base_stats=self.BASE_STATS,
            level=self.LEVEL,
            min_advance=1700,
            max_advance=1710,
        )
        assert seed == "557B"
        assert advance == 1708

    def test_real_data_hasty_unique_narrow(self):
        """実機データ: せっかち (Hasty) — 狭い範囲で一意に特定できるケース

        実機観測値:
            Stats: HP=231, Atk=133, Def=171, SpA=145, SpD=233, Spe=174
            IV: H=5, A=4, B=7, C=20, D=18, S=1
            初期Seed=0x87B5, advance=1708, LCG state=0xA4B0A931

        ※ 同一ステータスの別候補 (seed=0xCA28, adv=12193) が存在するが、
           狭い探索範囲では 0x87B5 のみがヒットする。
        """
        seed, advance = solve_initial_seed(
            observed_stats=(231, 133, 171, 145, 233, 174),
            base_stats=self.BASE_STATS,
            level=self.LEVEL,
            min_advance=1700,
            max_advance=1710,
        )
        assert seed == "87B5"
        assert advance == 1708

    def test_real_data_hasty_multiple_seeds(self):
        """実機データ: せっかち (Hasty) — 広い範囲で複数候補となるケース

        同一ステータスに対して 2 つの (seed, advance) が存在する:
            1. seed=0x87B5, advance=1708
            2. seed=0xCA28, advance=12193
        両方が探索範囲に含まれる場合、"MULT" を返す。
        """
        seed, advance = solve_initial_seed(
            observed_stats=(231, 133, 171, 145, 233, 174),
            base_stats=self.BASE_STATS,
            level=self.LEVEL,
            min_advance=1700,
            max_advance=12200,
        )
        assert seed == "MULT"
        assert advance is None

    def test_real_data_jolly_forward_consistency(self):
        """実機データ: 順方向生成と逆算結果の一貫性検証

        seed=0x557B から advance=1708 で生成した個体のステータスが
        実機観測値と一致することを確認する。
        """
        lcg = LCG32(0x557B)
        lcg.advance(1708)
        assert lcg.seed == 0x35D25317  # 生成直前の LCG state

        pokemon = generate_pokemon(lcg)
        assert pokemon.nature_id == NATURE_TO_ID["Jolly"]

        # IV が実機観測の範囲内
        assert pokemon.iv_hp == 5
        assert pokemon.iv_atk == 27
        assert pokemon.iv_def == 25
        assert pokemon.iv_spa == 3
        assert pokemon.iv_spd == 28
        assert pokemon.iv_spe == 10

        mult = get_nature_multipliers("Jolly")
        stats = pokemon.calc_stats(self.BASE_STATS, self.LEVEL, mult)
        assert stats == (231, 149, 204, 119, 240, 182)

    def test_real_data_hasty_forward_consistency(self):
        """実機データ: 順方向生成と逆算結果の一貫性検証 (Hasty, 2 候補)

        2 つの (seed, advance) ペアがそれぞれ同一ステータスを生成することを確認する。
        """
        expected_stats = (231, 133, 171, 145, 233, 174)
        mult = get_nature_multipliers("Hasty")

        # 候補 1: seed=0x87B5, advance=1708
        lcg1 = LCG32(0x87B5)
        lcg1.advance(1708)
        assert lcg1.seed == 0xA4B0A931
        p1 = generate_pokemon(lcg1)
        assert p1.nature_id == NATURE_TO_ID["Hasty"]
        assert p1.calc_stats(self.BASE_STATS, self.LEVEL, mult) == expected_stats

        # 候補 2: seed=0xCA28, advance=12193
        lcg2 = LCG32(0xCA28)
        lcg2.advance(12193)
        assert lcg2.seed == 0x8ACEDC9B
        p2 = generate_pokemon(lcg2)
        assert p2.nature_id == NATURE_TO_ID["Hasty"]
        assert p2.calc_stats(self.BASE_STATS, self.LEVEL, mult) == expected_stats

        # 異なる IV で同一ステータスになるケース
        assert p1.pid != p2.pid


# ============================================================
# config テスト
# ============================================================

from frlg_initial_seed.config import FrlgInitialSeedConfig, KeyInput


class TestConfig:
    """設定パラメータのテスト"""

    def test_defaults(self):
        """デフォルト値が正しく設定される"""
        cfg = FrlgInitialSeedConfig()
        assert cfg.language == "JPN"
        assert cfg.rom == "FR"
        assert cfg.device == "Switch"
        assert cfg.min_frame == 2000
        assert cfg.max_frame == 2180
        assert cfg.trials == 3
        assert cfg.frame2 == 560
        assert cfg.fps == 60.0
        assert cfg.base_stats == (106, 90, 130, 90, 154, 110)
        assert cfg.level == 70
        assert cfg.keyinput is KeyInput.NONE

    def test_file_name_removed(self):
        """ファイル名は固定 (initial_seeds.csv) になったため file_name プロパティが存在しない"""
        cfg = FrlgInitialSeedConfig()
        assert not hasattr(cfg, "file_name")

    def test_from_args(self):
        """args dict から設定が構築される"""
        args = {
            "language": "ENG",
            "rom": "LG",
            "device": "GC",
            "min_frame": 3000,
            "max_frame": 3500,
            "trials": 3,
            "sound_mode": "ステレオ",
            "keyinput": "dpad_on_boot",
        }
        cfg = FrlgInitialSeedConfig.from_args(args)
        assert cfg.language == "ENG"
        assert cfg.rom == "LG"
        assert cfg.device == "GC"
        assert cfg.min_frame == 3000
        assert cfg.max_frame == 3500
        assert cfg.trials == 3
        assert cfg.sound_mode == "ステレオ"
        assert cfg.keyinput is KeyInput.DPAD_ON_BOOT
        # 指定しなかった値はデフォルト
        assert cfg.frame2 == 560
        assert cfg.button_mode == "ヘルプ"

    def test_from_args_base_stats(self):
        """args dict から base_stats が構築される"""
        args = {"base_stats": [100, 80, 120, 80, 140, 100]}
        cfg = FrlgInitialSeedConfig.from_args(args)
        assert cfg.base_stats == (100, 80, 120, 80, 140, 100)


# ============================================================
# CSV ヘルパーテスト
# ============================================================

from frlg_initial_seed.csv_helper import (
    append_csv_row,
    build_csv_path,
    CSV_FIELDNAMES,
    CSV_FILENAME,
)


class TestCSVHelper:
    """CSV 読み書きのテスト"""

    def test_build_csv_path_fixed(self):
        """固定ファイル名 initial_seeds.csv が返る"""
        cfg = FrlgInitialSeedConfig()
        path = build_csv_path(cfg)
        expected = Path("static/frlg_initial_seed") / CSV_FILENAME
        assert path == expected

    def test_append_creates_with_header(self, tmp_path):
        """ファイルが存在しない場合、ヘッダー付きで作成される"""
        csv_path = tmp_path / CSV_FILENAME
        append_csv_row(csv_path, {
            "frame": "2120", "seed": "72C2", "advance": "1340",
            "region": "JPN", "version": "FR", "edition": "Switch",
            "sound_mode": "モノラル", "button_mode": "ヘルプ", "keyinput": "none",
        })

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            assert reader.fieldnames == CSV_FIELDNAMES
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["frame"] == "2120"
        assert rows[0]["seed"] == "72C2"

    def test_append_does_not_duplicate_header(self, tmp_path):
        """複数回 append してもヘッダーは 1 回のみ"""
        csv_path = tmp_path / CSV_FILENAME
        for seed in ("AAAA", "BBBB"):
            append_csv_row(csv_path, {
                "frame": "2120", "seed": seed, "advance": "1340",
                "region": "JPN", "version": "FR", "edition": "Switch",
                "sound_mode": "モノラル", "button_mode": "ヘルプ", "keyinput": "none",
            })

        with open(csv_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        # ヘッダー 1 行 + データ 2 行
        assert len(lines) == 3

    def test_csv_contains_metadata_columns(self, tmp_path):
        """CSV に region/version/edition/sound_mode/button_mode/keyinput が含まれる"""
        csv_path = tmp_path / CSV_FILENAME
        append_csv_row(csv_path, {
            "frame": "2120", "seed": "72C2", "advance": "1340",
            "region": "JPN", "version": "FR", "edition": "Switch",
            "sound_mode": "モノラル", "button_mode": "ヘルプ", "keyinput": "none",
        })

        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
        assert "region" in fieldnames
        assert "version" in fieldnames
        assert "edition" in fieldnames
        assert "sound_mode" in fieldnames
        assert "button_mode" in fieldnames
        assert "keyinput" in fieldnames

