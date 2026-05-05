from dataclasses import dataclass

from nyxpy.framework.core.hardware.protocol import (
    CH552SerialProtocol,
    PokeConSerialProtocol,
    SerialProtocolInterface,
    ThreeDSSerialProtocol,
)


@dataclass(frozen=True)
class ProtocolDescriptor:
    name: str
    protocol_cls: type[SerialProtocolInterface]
    default_baudrate: int
    supported_baudrates: tuple[int, ...]
    aliases: tuple[str, ...] = ()


class ProtocolFactory:
    """
    シリアルプロトコルのファクトリークラス。
    プロトコル名から対応するプロトコル実装と接続メタデータを解決する。
    """

    _descriptors: dict[str, ProtocolDescriptor] = {
        "CH552": ProtocolDescriptor(
            name="CH552",
            protocol_cls=CH552SerialProtocol,
            default_baudrate=9600,
            supported_baudrates=(9600,),
            aliases=("CH552SERIAL",),
        ),
        "PokeCon": ProtocolDescriptor(
            name="PokeCon",
            protocol_cls=PokeConSerialProtocol,
            default_baudrate=9600,
            supported_baudrates=(9600, 19200, 38400, 57600, 115200),
        ),
        "3DS": ProtocolDescriptor(
            name="3DS",
            protocol_cls=ThreeDSSerialProtocol,
            default_baudrate=115200,
            supported_baudrates=(9600, 19200, 57600, 115200),
            aliases=("THREEDS", "NINTENDO3DS"),
        ),
    }

    @classmethod
    def get_protocol_names(cls) -> list[str]:
        """
        利用可能なプロトコル名のリストを取得する。

        :return: プロトコル名のリスト
        """
        return list(cls._descriptors.keys())

    @classmethod
    def get_descriptor(cls, protocol_name: str) -> ProtocolDescriptor:
        """
        指定されたプロトコル名のメタデータを取得する。

        :param protocol_name: プロトコル名
        :return: プロトコルメタデータ
        :raises ValueError: 未知のプロトコル名を指定した場合
        """
        if not protocol_name:
            raise ValueError("Protocol name cannot be empty")

        normalized = protocol_name.upper()
        for descriptor in cls._descriptors.values():
            names = (descriptor.name.upper(), *descriptor.aliases)
            if normalized in names:
                return descriptor
        raise ValueError(f"Unknown protocol: {protocol_name}")

    @classmethod
    def get_default_baudrate(cls, protocol_name: str) -> int:
        """
        指定されたプロトコルの既定ボーレートを取得する。

        :param protocol_name: プロトコル名
        :return: 既定ボーレート
        """
        return cls.get_descriptor(protocol_name).default_baudrate

    @classmethod
    def resolve_baudrate(cls, protocol_name: str, baudrate: int | None = None) -> int:
        """
        明示ボーレートまたはプロトコル既定値から接続ボーレートを決定する。

        :param protocol_name: プロトコル名
        :param baudrate: 明示ボーレート。None の場合は既定値を返す
        :return: 接続ボーレート
        :raises ValueError: プロトコルが対応しないボーレートを指定した場合
        """
        descriptor = cls.get_descriptor(protocol_name)
        resolved = descriptor.default_baudrate if baudrate is None else baudrate
        if resolved not in descriptor.supported_baudrates:
            supported = ", ".join(str(value) for value in descriptor.supported_baudrates)
            raise ValueError(
                f"Unsupported baudrate {resolved} for protocol {descriptor.name}. "
                f"Supported baudrates: {supported}"
            )
        return resolved

    @classmethod
    def create_protocol(cls, protocol_name: str) -> SerialProtocolInterface:
        """
        指定されたプロトコル名に対応するプロトコルのインスタンスを生成する。

        :param protocol_name: プロトコル名
        :return: シリアルプロトコルインターフェースの実装
        :raises ValueError: 未知のプロトコル名を指定した場合
        """
        return cls.get_descriptor(protocol_name).protocol_cls()
