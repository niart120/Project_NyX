from pathlib import Path

from mkdocs.commands.build import build
from mkdocs.config import load_config

from nyxpy.__main__ import parse_arguments


def test_swbt_docs_examples_match_cli_parser() -> None:
    docs = Path("docs/user-guide/cli.md").read_text(encoding="utf-8")
    examples = (
        ("nyxpy swbt adapters", ["swbt", "adapters"]),
        ("nyxpy swbt adapters --json", ["swbt", "adapters", "--json"]),
        (
            "nyxpy swbt pair --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json",
            [
                "swbt",
                "pair",
                "--adapter",
                "usb:0",
                "--controller-type",
                "pro-controller",
                "--key-store",
                ".nyxpy/swbt/pro-controller-bond.json",
            ],
        ),
        (
            "nyxpy swbt reconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json",
            [
                "swbt",
                "reconnect",
                "--adapter",
                "usb:0",
                "--controller-type",
                "pro-controller",
                "--key-store",
                ".nyxpy/swbt/pro-controller-bond.json",
            ],
        ),
        (
            'nyxpy run sample_macro --controller swbt --swbt-adapter usb:0 --swbt-controller-type pro-controller --swbt-key-store .nyxpy/swbt/pro-controller-bond.json --capture "Capture Device"',
            [
                "run",
                "sample_macro",
                "--controller",
                "swbt",
                "--swbt-adapter",
                "usb:0",
                "--swbt-controller-type",
                "pro-controller",
                "--swbt-key-store",
                ".nyxpy/swbt/pro-controller-bond.json",
                "--capture",
                "Capture Device",
            ],
        ),
    )

    for command, argv in examples:
        assert command in docs
        assert parse_arguments(argv).command in {"run", "swbt"}


def test_public_docs_do_not_advertise_process_local_swbt_disconnect() -> None:
    paths = (
        Path("docs/user-guide/cli.md"),
        Path("docs/architecture/swbt-integration/architecture.md"),
        Path("docs/architecture/swbt-integration/testing.md"),
        Path("docs/architecture/swbt-integration/testing-rollout.md"),
    )

    for path in paths:
        assert "nyxpy swbt disconnect" not in path.read_text(encoding="utf-8"), path


def test_mkdocs_build_includes_swbt_pages(tmp_path: Path) -> None:
    config = load_config(
        config_file="mkdocs.yml",
        site_dir=str(tmp_path / "site"),
        strict=True,
    )

    build(config)

    output_root = tmp_path / "site" / "architecture" / "swbt-integration"
    for source in Path("docs/architecture/swbt-integration").glob("*.md"):
        output = (
            output_root / "index.html"
            if source.name == "index.md"
            else output_root / source.stem / "index.html"
        )
        assert output.is_file(), source
