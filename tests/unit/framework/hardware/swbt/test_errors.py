import pytest
from swbt import (
    AdapterIdentityRecoveryRequired,
    InvalidKeyStoreError,
    InvalidProfileError,
    ProfileControllerMismatchError,
)

from nyxpy.framework.core.hardware.swbt.errors import (
    map_swbt_exception,
    swbt_user_error_message,
)
from nyxpy.framework.core.macro.exceptions import ConfigurationError


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (FileNotFoundError("missing"), "NYX_SWBT_PROFILE_NOT_FOUND"),
        (FileExistsError("exists"), "NYX_SWBT_PROFILE_ALREADY_EXISTS"),
        (InvalidProfileError("schema v1"), "NYX_SWBT_PROFILE_INVALID"),
        (
            ProfileControllerMismatchError(
                expected_controller_kind="pro-controller",
                actual_controller_kind="joy-con-l",
            ),
            "NYX_SWBT_PROFILE_CONTROLLER_MISMATCH",
        ),
        (InvalidKeyStoreError("invalid key"), "NYX_SWBT_PROFILE_KEY_DATA_INVALID"),
        (
            AdapterIdentityRecoveryRequired(
                target_address="02:00:00:00:00:01",
                stage="reset",
            ),
            "NYX_SWBT_ADAPTER_IDENTITY_RECOVERY_REQUIRED",
        ),
    ],
)
def test_profile_errors_map_to_individual_nyx_codes(
    error: BaseException,
    code: str,
) -> None:
    mapped = map_swbt_exception(error, component="test")

    assert mapped.code == code


def test_adapter_identity_recovery_message_requests_usb_reconnect() -> None:
    mapped = map_swbt_exception(
        AdapterIdentityRecoveryRequired(
            target_address="02:00:00:00:00:01",
            stage="reset",
        ),
        component="test",
    )

    assert "unplug and reconnect the USB Bluetooth dongle" in str(mapped)


def test_user_error_message_finds_profile_error_in_nested_cleanup_group() -> None:
    profile_error = ConfigurationError(
        "pairing profile uses an unsupported schema",
        code="NYX_SWBT_PROFILE_INVALID",
        component="test",
    )
    error = ExceptionGroup("connection and cleanup failed", [profile_error, RuntimeError("close")])

    assert swbt_user_error_message(error) == (
        "NYX_SWBT_PROFILE_INVALID: pairing profile uses an unsupported schema"
    )
