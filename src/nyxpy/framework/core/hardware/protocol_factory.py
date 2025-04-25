from nyxpy.framework.core.hardware.protocol import SerialProtocolInterface, CH552SerialProtocol, PokeConSerialProtocol
from typing import Dict, Type

class ProtocolFactory:
    """
    シリアルプロトコルのファクトリークラス
    プロトコル名から対応するプロトコル実装のインスタンスを生成する
    """
    
    # 利用可能なプロトコル実装のマッピング
    _protocols: Dict[str, Type[SerialProtocolInterface]] = {
        "CH552": CH552SerialProtocol,
        "PokeCon": PokeConSerialProtocol,
    }
    
    @classmethod
    def get_protocol_names(cls) -> list[str]:
        """
        利用可能なプロトコル名のリストを取得する
        
        :return: プロトコル名のリスト
        """
        return list(cls._protocols.keys())
    
    @classmethod
    def create_protocol(cls, protocol_name: str) -> SerialProtocolInterface:
        """
        指定されたプロトコル名に対応するプロトコルのインスタンスを生成する
        
        :param protocol_name: プロトコル名
        :return: シリアルプロトコルインターフェースの実装
        :raises ValueError: 未知のプロトコル名を指定した場合
        """
        if protocol_name not in cls._protocols:
            # デフォルトで CH552 プロトコルを使用する
            return CH552SerialProtocol()
        
        # プロトコル名に対応するクラスをインスタンス化
        return cls._protocols[protocol_name]()