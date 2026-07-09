from pathlib import Path

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
            "nyxpy swbt disconnect --adapter usb:0 --controller-type pro-controller --key-store .nyxpy/swbt/pro-controller-bond.json",
            [
                "swbt",
                "disconnect",
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
